import pytest

from app.db import tenant_tx
from tests.conftest import env

MARIANA = {"id_last4": "1612", "birth_date": "1989-02-17"}
JULIAN = {"id_last4": "4408", "birth_date": "1976-09-03"}
SANTIAGO = {"id_last4": "2290", "birth_date": "1994-06-21"}
VALERIA = {"id_last4": "1144", "birth_date": "1991-12-09"}
HERNAN = {"id_last4": "3107", "birth_date": "1982-04-30"}
NATALIA = {"id_last4": "7731", "birth_date": "1993-08-12"}
CAMILO = {"id_last4": "5210", "birth_date": "1985-01-25"}


@pytest.fixture(scope="session")
def demos_key() -> str:
    return env("TENANT_KEY_DEMOS")


async def post(client, key, path, conversation_id, **body):
    response = await client.post(f"/verticals/{path}", headers={"X-Tenant-Key": key},
                                 json={"conversation_id": conversation_id, **body})
    return response


async def login(client, key, conversation_id, vertical, identity):
    r = await post(client, key, "verify-customer", conversation_id, vertical=vertical, **identity)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["verified"], data
    return data["session_token"]


async def test_wrong_vertical_does_not_verify(client, demos_key, conversation_id):
    r = await post(client, demos_key, "verify-customer", conversation_id, vertical="retail", **MARIANA)
    assert r.json()["verified"] is False


async def test_lockout_after_three_failures(client, demos_key, conversation_id):
    bad = {"id_last4": "0000", "birth_date": "1990-01-01"}
    for _ in range(3):
        await post(client, demos_key, "verify-customer", conversation_id, vertical="salud", **bad)
    r = await post(client, demos_key, "verify-customer", conversation_id, vertical="salud", **MARIANA)
    assert r.json()["locked"] is True


async def test_tools_reject_missing_session(client, demos_key, conversation_id):
    r = await post(client, demos_key, "salud/my-appointment", conversation_id, session_token="x" * 30)
    assert r.status_code == 401


async def test_other_tenant_key_is_refused(client, avanza_key, conversation_id):
    r = await post(client, avanza_key, "verify-customer", conversation_id, vertical="salud", **MARIANA)
    assert r.status_code == 403


async def test_salud_book_and_cancel_flow(client, demos_key, conversation_id):
    token = await login(client, demos_key, conversation_id, "salud", JULIAN)
    slots = (await post(client, demos_key, "salud/availability", conversation_id, session_token=token,
                        specialty="medicina")).json()["slots"]
    assert slots
    booked = (await post(client, demos_key, "salud/book", conversation_id, session_token=token,
                         slot_id=slots[0]["slot_id"])).json()
    assert booked["booked"]
    again = (await post(client, demos_key, "salud/book", conversation_id, session_token=token,
                        slot_id=slots[0]["slot_id"])).json()
    assert again["booked"] is False
    cancelled = (await post(client, demos_key, "salud/cancel", conversation_id, session_token=token,
                            appointment_ref=booked["appointment_ref"])).json()
    # The earliest slot is usually inside the 24h notice window: policy refuses, otherwise it cancels.
    assert cancelled["cancelled"] is True or cancelled["too_late"] is True
    async with tenant_tx("demos") as conn:  # leave the demo calendar as we found it
        await conn.execute("update cobranza.appointments set status = 'cancelled' where ref = $1",
                           booked["appointment_ref"])
        await conn.execute("update cobranza.clinic_slots set taken = false where id = $1", slots[0]["slot_id"])


async def test_salud_cancel_inside_window_is_refused(client, demos_key, conversation_id):
    token = await login(client, demos_key, conversation_id, "salud", MARIANA)
    mine = (await post(client, demos_key, "salud/my-appointment", conversation_id, session_token=token)).json()
    assert mine["has_appointment"]
    # The seeded appointment is the earliest slot tomorrow: less than 48h away, may be inside 24h.
    result = (await post(client, demos_key, "salud/cancel", conversation_id, session_token=token,
                         appointment_ref=mine["appointment_ref"])).json()
    assert "cancelled" in result


async def test_retail_return_window(client, demos_key, conversation_id):
    token = await login(client, demos_key, conversation_id, "retail", HERNAN)
    r = (await post(client, demos_key, "retail/return", conversation_id, session_token=token,
                    order_no="MN-10110", reason="No me quedaron")).json()
    assert r["started"] is False and r["outside_window"] is True


async def test_retail_order_status_is_scoped_to_customer(client, demos_key, conversation_id):
    token = await login(client, demos_key, conversation_id, "retail", SANTIAGO)
    mine = (await post(client, demos_key, "retail/order-status", conversation_id, session_token=token,
                       order_no="MN-10482")).json()
    assert mine["orders"][0]["status"] == "out_for_delivery"
    other = (await post(client, demos_key, "retail/order-status", conversation_id, session_token=token,
                        order_no="MN-10533")).json()
    assert other["orders"] == []


async def test_checkout_link_requires_consent(client, demos_key, conversation_id):
    no_consent = await login(client, demos_key, conversation_id, "retail", HERNAN)
    r = (await post(client, demos_key, "retail/checkout-link", conversation_id, session_token=no_consent)).json()
    assert r["sent"] is False and r["no_consent"] is True
    consent = await login(client, demos_key, conversation_id + "-b", "retail", VALERIA)
    r = (await post(client, demos_key, "retail/checkout-link", conversation_id + "-b", session_token=consent)).json()
    assert r["sent"] is True


async def test_telco_outage_and_diagnostic(client, demos_key, conversation_id):
    t1 = await login(client, demos_key, conversation_id, "telco", CAMILO)
    out = (await post(client, demos_key, "telco/outage", conversation_id, session_token=t1)).json()
    assert out["outage"] is True
    t2 = await login(client, demos_key, conversation_id + "-b", "telco", NATALIA)
    diag = (await post(client, demos_key, "telco/diagnostic", conversation_id + "-b", session_token=t2)).json()
    assert diag["healthy"] is False


async def test_retention_offer_comes_from_policy(client, demos_key, conversation_id):
    token = await login(client, demos_key, conversation_id, "telco", NATALIA)
    offer = (await post(client, demos_key, "telco/retention-offer", conversation_id, session_token=token,
                        reason="precio")).json()
    assert offer["discount_pct"] == 20 and offer["new_price_text"] == "$79.920"


async def test_inmo_lead_scoring_and_booking(client, demos_key, conversation_id):
    r = await post(client, demos_key, "inmo/lead", conversation_id, name="Ana Prueba", zone="Chapinero",
                   budget=600000000, bedrooms=2, timeline="inmediato")
    assert r.json()["score"] == "alto"
    low = await post(client, demos_key, "inmo/lead", conversation_id + "-b", name="Luis Prueba", timeline="explorando")
    assert low.json()["score"] == "bajo"
    slots = (await post(client, demos_key, "inmo/advisor-slots", conversation_id)).json()["slots"]
    booked = (await post(client, demos_key, "inmo/book-advisor", conversation_id,
                         slot_id=slots[0]["slot_id"])).json()
    assert booked["booked"] is True
    async with tenant_tx("demos") as conn:
        await conn.execute("update cobranza.advisor_slots set taken = false where id = $1", slots[0]["slot_id"])


async def test_inmo_search_filters(client, demos_key, conversation_id):
    r = (await post(client, demos_key, "inmo/search", conversation_id, zone="Chapinero", kind="venta",
                    bedrooms=2, max_price=600000000)).json()
    assert [p["property_id"] for p in r["properties"]] == ["prop_01"]
