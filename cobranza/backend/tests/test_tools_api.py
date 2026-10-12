"""Integration tests against the real Supabase database, connected as the RLS-bound app role."""

import re

import asyncpg
import pytest

from app.config import get_settings
from app.db import connection, tenant_tx
from tests.conftest import FIXTURE, FIXTURE_ACCOUNT, LAURA, audit_rows, verify


def h(key: str) -> dict:
    return {"X-Tenant-Key": key}


async def test_happy_path_verify_options_plan_link_and_pay(client, avanza_key, conversation_id):
    verified = await verify(client, avanza_key, conversation_id, LAURA)
    assert verified["verified"] is True
    assert verified["customer_first_name"] == "Laura"
    token = verified["session_token"]
    base = {"conversation_id": conversation_id, "session_token": token}

    summary = (await client.post("/tools/account-summary", headers=h(avanza_key), json=base)).json()
    assert summary["account"] == "terminada en 4417"
    assert summary["overdue_amount_text"] == "$1.200.000"
    assert summary["days_past_due"] == 21
    assert "1020304417" not in str(summary)  # full national id never leaves the vault

    options = (await client.post("/tools/payment-options", headers=h(avanza_key), json=base)).json()
    assert options["discounts_available"] is False
    kinds = {o["kind"]: o for o in options["options"]}
    assert set(kinds) == {"full", "installments", "hardship"}
    assert kinds["installments"]["installment_amount_text"] == "$400.000"
    chosen = kinds["installments"]["plan_id"]

    plan_body = {**base, "plan_id": chosen, "idempotency_key": conversation_id}
    plan = (await client.post("/tools/payment-plans", headers=h(avanza_key), json=plan_body)).json()
    assert re.fullmatch(r"AVA-P-[2-9A-Z]{6}", plan["plan_ref"])
    assert plan["idempotent_replay"] is False

    replay = (await client.post("/tools/payment-plans", headers=h(avanza_key), json=plan_body)).json()
    assert replay["plan_ref"] == plan["plan_ref"] and replay["idempotent_replay"] is True

    link_body = {**base, "plan_ref": plan["plan_ref"]}
    link = (await client.post("/tools/payment-link", headers=h(avanza_key), json=link_body)).json()
    assert link == {"sent": True, "channel": "whatsapp", "recipient": link["recipient"], "already_sent": False}
    again = (await client.post("/tools/payment-link", headers=h(avanza_key), json=link_body)).json()
    assert again["already_sent"] is True

    async with tenant_tx("avanza") as conn:
        link_token = await conn.fetchval(
            "select link_token from cobranza.payment_links where plan_ref = $1", plan["plan_ref"])
        plans = await conn.fetchval(
            "select count(*) from cobranza.payment_plans where idempotency_key = $1", conversation_id)
    assert plans == 1

    page = await client.get(f"/pay/{link_token}")
    assert page.status_code == 200
    assert '<html lang="es">' in page.text and "<main>" in page.text and "<dl>" in page.text
    assert "3 cuotas de $400.000" in page.text
    paid = await client.post(f"/pay/{link_token}")
    assert paid.status_code == 200 and "Pago recibido" in paid.text

    tools = [(r["tool"], r["result"]) for r in await audit_rows("avanza", conversation_id)]
    assert tools == [
        ("verify_identity", "verified"),
        ("get_account_summary", "ok"),
        ("get_payment_options", "ok"),
        ("create_payment_plan", "created"),
        ("create_payment_plan", "idempotent_replay"),
        ("send_payment_link", "sent"),
        ("send_payment_link", "idempotent_replay"),
    ]


async def test_account_tools_require_a_verified_session(client, avanza_key, conversation_id):
    missing = await client.post("/tools/account-summary", headers=h(avanza_key),
                                json={"conversation_id": conversation_id})
    assert missing.status_code == 422 and missing.json()["fields"] == ["session_token"]

    forged = await client.post("/tools/account-summary", headers=h(avanza_key),
                               json={"conversation_id": conversation_id, "session_token": "st_" + "x" * 40})
    assert forged.status_code == 401 and forged.json()["error"] == "invalid_session"
    assert ("get_account_summary", "rejected:invalid_session") in [
        (r["tool"], r["result"]) for r in await audit_rows("avanza", conversation_id)]


async def test_failed_identity_reveals_nothing_and_locks_after_three(client, avanza_key, conversation_id):
    wrong = {"id_last4": "4417", "birth_date": "1991-01-01"}
    for remaining in (2, 1, 0):
        result = await verify(client, avanza_key, conversation_id, wrong)
        assert result["verified"] is False and result["session_token"] == ""
        assert result["customer_first_name"] == "" and result["attempts_remaining"] == remaining
    locked = await verify(client, avanza_key, conversation_id, LAURA)  # even correct data is refused now
    assert locked["verified"] is False and locked["locked"] is True


async def test_malformed_identity_is_rejected_by_validation(client, avanza_key, conversation_id):
    response = await client.post("/tools/verify-identity", headers=h(avanza_key), json={
        "conversation_id": conversation_id, "id_last4": "cuatro", "birth_date": "14/05/1990"})
    assert response.status_code == 422
    assert response.json()["fields"] == ["birth_date", "id_last4"]
    assert "cuatro" not in response.text


async def test_invented_or_foreign_plan_ids_are_rejected(client, avanza_key, conversation_id):
    token = (await verify(client, avanza_key, conversation_id, LAURA))["session_token"]
    base = {"conversation_id": conversation_id, "session_token": token, "idempotency_key": conversation_id}

    invented = await client.post("/tools/payment-plans", headers=h(avanza_key),
                                 json={**base, "plan_id": "pln_DESCVENTA9ZZ"})
    assert invented.status_code == 422 and invented.json()["error"] == "plan_not_offered"

    other_conversation = conversation_id + "-b"
    other_token = (await verify(client, avanza_key, other_conversation, LAURA))["session_token"]
    other_options = (await client.post("/tools/payment-options", headers=h(avanza_key), json={
        "conversation_id": other_conversation, "session_token": other_token})).json()
    foreign = await client.post("/tools/payment-plans", headers=h(avanza_key),
                                json={**base, "plan_id": other_options["options"][0]["plan_id"]})
    assert foreign.status_code == 422 and foreign.json()["error"] == "plan_not_offered"


async def test_same_idempotency_key_with_another_plan_conflicts(client, avanza_key, conversation_id):
    token = (await verify(client, avanza_key, conversation_id, LAURA))["session_token"]
    base = {"conversation_id": conversation_id, "session_token": token}
    options = (await client.post("/tools/payment-options", headers=h(avanza_key), json=base)).json()["options"]
    first = await client.post("/tools/payment-plans", headers=h(avanza_key), json={
        **base, "plan_id": options[0]["plan_id"], "idempotency_key": conversation_id})
    assert first.status_code == 200
    second = await client.post("/tools/payment-plans", headers=h(avanza_key), json={
        **base, "plan_id": options[1]["plan_id"], "idempotency_key": conversation_id})
    assert second.status_code == 409 and second.json()["error"] == "idempotency_conflict"


async def test_tenant_isolation_token_from_avanza_with_nexo_key(client, avanza_key, nexo_key, conversation_id):
    avanza_token = (await verify(client, avanza_key, conversation_id, LAURA))["session_token"]
    crossed = await client.post("/tools/account-summary", headers=h(nexo_key), json={
        "conversation_id": conversation_id, "session_token": avanza_token})
    assert crossed.status_code == 401
    assert ("get_account_summary", "rejected:invalid_session") in [
        (r["tool"], r["result"]) for r in await audit_rows("nexo", conversation_id)]

    # Same identity data under Nexo's key reaches Nexo's own customer, never Avanza's.
    nexo_conv = conversation_id + "-nexo"
    nexo = await verify(client, nexo_key, nexo_conv, LAURA)
    assert nexo["customer_first_name"] == "Andrés"
    summary = (await client.post("/tools/account-summary", headers=h(nexo_key), json={
        "conversation_id": nexo_conv, "session_token": nexo["session_token"]})).json()
    assert summary["account_last4"] == "3381"
    options = (await client.post("/tools/payment-options", headers=h(nexo_key), json={
        "conversation_id": nexo_conv, "session_token": nexo["session_token"]})).json()
    assert [o["kind"] for o in options["options"]] == ["full", "installments"]


async def test_tenant_credentials(client, avanza_key, conversation_id):
    body = {"conversation_id": conversation_id, **LAURA}
    assert (await client.post("/tools/verify-identity", json=body)).status_code == 401
    assert (await client.post("/tools/verify-identity", headers=h("tk_fake"), json=body)).status_code == 401
    mismatch = await client.post("/tools/verify-identity",
                                 headers={**h(avanza_key), "X-Tenant-Id": "nexo"}, json=body)
    assert mismatch.status_code == 403 and mismatch.json()["error"] == "tenant_mismatch"


async def test_row_level_security_at_the_database():
    async with connection() as conn:
        assert await conn.fetchval("select rolbypassrls from pg_roles where rolname = current_user") is False
        async with conn.transaction():
            assert await conn.fetchval("select count(*) from cobranza.accounts") == 0
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id', 'nexo', true)")
            tenants = await conn.fetch("select distinct tenant_id from cobranza.accounts")
            assert [r["tenant_id"] for r in tenants] == ["nexo"]
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("select * from cobranza.pii_vault")
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id', 'nexo', true)")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute("""insert into cobranza.audit_log (tenant_id, tool, result)
                                      values ('avanza', 'forged', 'forged')""")


async def test_dispute_pauses_collection(client, avanza_key, conversation_id, reset_fixture_account):
    token = (await verify(client, avanza_key, conversation_id, FIXTURE))["session_token"]
    base = {"conversation_id": conversation_id, "session_token": token}
    dispute = await client.post("/tools/disputes", headers=h(avanza_key),
                                json={**base, "reason": "Dice que ya pagó la cuota de septiembre"})
    assert dispute.status_code == 200 and dispute.json()["case_ref"].startswith("AVA-D-")
    blocked = await client.post("/tools/payment-options", headers=h(avanza_key), json=base)
    assert blocked.status_code == 409 and blocked.json()["error"] == "account_in_dispute"


async def test_opt_out_linked_and_unlinked(client, avanza_key, nexo_key, conversation_id):
    await verify(client, avanza_key, conversation_id, FIXTURE)
    linked = (await client.post("/tools/opt-out", headers=h(avanza_key), json={
        "conversation_id": conversation_id})).json()
    assert linked["registered"] is True and linked["linked_to_account"] is True

    unlinked = (await client.post("/tools/opt-out", headers=h(avanza_key), json={
        "conversation_id": conversation_id + "-anon"})).json()
    assert unlinked["registered"] is True and unlinked["linked_to_account"] is False

    other_tenant = (await client.post("/tools/opt-out", headers=h(nexo_key), json={
        "conversation_id": conversation_id})).json()
    assert other_tenant["linked_to_account"] is False

    window = (await client.get("/compliance/contact-window", headers=h(avanza_key), params={
        "account_id": FIXTURE_ACCOUNT, "at": "2026-10-13T10:00:00-05:00"})).json()
    assert window["allowed"] is False and window["reasons"] == ["customer_opted_out"]


async def test_callback_without_verification(client, avanza_key, conversation_id):
    response = await client.post("/tools/callbacks", headers=h(avanza_key), json={
        "conversation_id": conversation_id, "reason": "Perdió el empleo y quiere hablar con un asesor",
        "preferred_window": "mañana en la mañana"})
    assert response.status_code == 200 and response.json()["callback_ref"].startswith("AVA-C-")


async def test_contact_window_endpoint(client, avanza_key):
    async def window(at: str, channel: str = "voice"):
        return (await client.get("/compliance/contact-window", headers=h(avanza_key), params={
            "account_id": "acc_avz_0002", "channel": channel, "at": at})).json()

    assert (await window("2026-10-13T10:00:00-05:00"))["allowed"] is True
    holiday = await window("2026-10-12T10:00:00-05:00")
    assert holiday["allowed"] is False and holiday["reasons"] == ["sunday_or_holiday"]
    assert holiday["next_allowed_at"] == "2026-10-13T07:00:00-05:00"
    night = await window("2026-10-14T20:30:00-05:00")
    assert night["reasons"] == ["outside_legal_hours"]

    unknown = await client.get("/compliance/contact-window", headers=h(avanza_key),
                               params={"account_id": "acc_nxo_0001"})
    assert unknown.status_code == 404  # another tenant's account does not exist for Avanza


async def test_post_call_webhook_stores_outcome(client, conversation_id):
    import hashlib
    import hmac
    import json
    import time

    secret = get_settings().post_call_webhook_secret
    if not secret:
        pytest.skip("POST_CALL_WEBHOOK_SECRET is not set")
    payload = {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {
            "agent_id": "agent_pytest_avanza",
            "conversation_id": conversation_id,
            "metadata": {"call_duration_secs": 201},
            "analysis": {
                "call_successful": "success",
                "evaluation_criteria_results": {"ai_disclosure": {"result": "success"}},
                "data_collection_results": {
                    "outcome": {"value": "promesa"}, "promise_amount": {"value": "$1.200.000"},
                    "promise_date": {"value": "2026-10-16"}, "late_reason": {"value": "Le pagaron tarde"},
                    "hardship": {"value": False}, "language": {"value": "es"},
                },
            },
        },
    }
    raw = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()

    bad = await client.post("/webhooks/post-call", content=raw,
                            headers={"elevenlabs-signature": f"t={ts},v0={'0' * 64}"})
    assert bad.status_code == 401

    ok = await client.post("/webhooks/post-call", content=raw,
                           headers={"elevenlabs-signature": f"t={ts},v0={sig}", "content-type": "application/json"})
    assert ok.json() == {"status": "stored"}
    async with tenant_tx("avanza") as conn:
        row = await conn.fetchrow("select * from cobranza.call_outcomes where conversation_id = $1", conversation_id)
    assert (row["outcome"], int(row["promise_amount"]), str(row["promise_date"]), row["duration_secs"]) == (
        "promesa", 1_200_000, "2026-10-16", 201)
    assert json.loads(row["evaluation"]) == {"ai_disclosure": "success"}
