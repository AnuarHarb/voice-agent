"""Webhook tools called by the ElevenLabs agent. Everything with consequences
(identity, money, compliance) is decided here; the agent only receives masked data."""

from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.db import tenant_tx
from app.fintech_sim.policy import Policy, payment_options
from app.integration.auth import Tenant, ToolError, audit, current_tenant
from app.integration.channels import ChannelError, PaymentLinkMessage, Recipient, get_channel
from app.integration.formatting import date_text, money_text
from app.integration.schemas import (
    AccountSummaryResponse,
    CallbackRequest,
    CallbackResponse,
    CreatePlanRequest,
    DisputeRequest,
    DisputeResponse,
    OptOutRequest,
    OptOutResponse,
    PaymentLinkRequest,
    PaymentLinkResponse,
    PaymentOptionOut,
    PaymentOptionsResponse,
    PaymentPlanResponse,
    SessionRequest,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from app.integration.security import (
    new_link_token,
    new_plan_id,
    new_ref,
    new_session_token,
    sha256_hex,
)

router = APIRouter(prefix="/tools", tags=["tools"])

_FREQUENCY = {"full": "pago único", "installments": "mensual", "hardship": "mensual"}


def _track(request: Request, tool: str, conversation_id: str) -> None:
    request.state.tool = tool
    request.state.conversation_id = conversation_id


async def _policy(conn: asyncpg.Connection) -> tuple[Policy, dict]:
    row = await conn.fetchrow("select * from cobranza.tenant_policies")
    if row is None:
        raise ToolError(500, "policy_missing", "Tenant has no credit policy configured.")
    policy = Policy(
        max_installments=row["max_installments"],
        min_installment_cop=row["min_installment_cop"],
        first_payment_max_days=row["first_payment_max_days"],
        hardship_enabled=row["hardship_enabled"],
        hardship_installments=row["hardship_installments"],
        hardship_grace_days=row["hardship_grace_days"],
    )
    return policy, dict(row)


async def _session_account(conn: asyncpg.Connection, token: str) -> str:
    """Identity first: account tools only work with a live token issued by verify_identity
    for this same tenant. Row level security hides other tenants' sessions."""
    account_id = await conn.fetchval(
        "select account_id from cobranza.sessions where token_hash = $1 and expires_at > now()",
        sha256_hex(token),
    )
    if account_id is None:
        raise ToolError(401, "invalid_session", "Identity is not verified for this conversation.")
    return account_id


async def _optional_account(conn: asyncpg.Connection, token: str, conversation_id: str) -> str | None:
    """Opt-out and callbacks work before verification. The agent has no session token yet at that
    point, so a verified session from the same conversation links the request to the account."""
    if token:
        return await _session_account(conn, token)
    return await conn.fetchval(
        """select account_id from cobranza.sessions
           where conversation_id = $1 and expires_at > now() order by created_at desc limit 1""",
        conversation_id,
    )


@router.post("/verify-identity", response_model=VerifyIdentityResponse)
async def verify_identity(
    body: VerifyIdentityRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> VerifyIdentityResponse:
    _track(request, "verify_identity", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        _, policy_row = await _policy(conn)
        max_attempts = policy_row["max_verification_attempts"]
        failures = await conn.fetchval(
            """select count(*) from cobranza.audit_log
               where tool = 'verify_identity' and result = 'not_verified'
                 and conversation_id = $1 and created_at > now() - interval '1 hour'""",
            body.conversation_id,
        )
        if failures >= max_attempts:
            await audit(tenant.id, body.conversation_id, "verify_identity", "locked", conn=conn)
            return VerifyIdentityResponse(
                verified=False, session_token="", attempts_remaining=0, locked=True,
                message="Too many failed attempts. Offer a callback with an advisor.",
            )

        last4, born = body.parsed()
        unreadable = [label for value, label in ((last4, "the last four digits of the cédula"),
                                                 (born, "the birth date with day, month and year")) if value is None]
        if unreadable:
            await audit(tenant.id, body.conversation_id, "verify_identity", "incomplete",
                        {"unreadable": len(unreadable)}, conn=conn)
            return VerifyIdentityResponse(
                verified=False, session_token="", attempts_remaining=max_attempts - failures, incomplete=True,
                message=f"Missing or unreadable: {' and '.join(unreadable)}. Ask the customer again for it.",
            )

        matches = await conn.fetch("select * from cobranza.match_identity($1, $2)", last4, born)
        if len(matches) != 1:
            await audit(tenant.id, body.conversation_id, "verify_identity", "not_verified",
                        {"ambiguous": len(matches) > 1}, conn=conn)
            remaining = max(max_attempts - failures - 1, 0)
            return VerifyIdentityResponse(
                verified=False, session_token="", attempts_remaining=remaining, locked=remaining == 0,
                message="The data does not match. Do not reveal whether an account exists.",
            )

        token = new_session_token()
        await conn.execute(
            """insert into cobranza.sessions (token_hash, tenant_id, account_id, conversation_id, expires_at)
               values ($1, $2, $3, $4, now() + make_interval(mins => $5))""",
            sha256_hex(token), tenant.id, matches[0]["account_id"], body.conversation_id,
            policy_row["session_ttl_minutes"],
        )
        await audit(tenant.id, body.conversation_id, "verify_identity", "verified", conn=conn)
    return VerifyIdentityResponse(
        verified=True, session_token=token, customer_first_name=matches[0]["first_name"],
        attempts_remaining=max_attempts - failures, message="Identity verified.",
    )


@router.post("/account-summary", response_model=AccountSummaryResponse)
async def account_summary(
    body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> AccountSummaryResponse:
    _track(request, "get_account_summary", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        account = await conn.fetchrow("select * from cobranza.accounts where id = $1", account_id)
        await audit(tenant.id, body.conversation_id, "get_account_summary", "ok", conn=conn)
    overdue, total = int(account["overdue_amount"]), int(account["total_balance"])
    return AccountSummaryResponse(
        account=f"terminada en {account['account_last4']}",
        account_last4=account["account_last4"],
        product=account["product"],
        overdue_amount=overdue,
        overdue_amount_text=money_text(overdue),
        total_balance=total,
        total_balance_text=money_text(total),
        days_past_due=account["days_past_due"],
        status=account["status"],
    )


@router.post("/payment-options", response_model=PaymentOptionsResponse)
async def get_payment_options(
    body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> PaymentOptionsResponse:
    _track(request, "get_payment_options", body.conversation_id)
    token_hash = sha256_hex(body.session_token)
    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        account = await conn.fetchrow("select * from cobranza.accounts where id = $1", account_id)
        if account["status"] == "in_dispute":
            raise ToolError(409, "account_in_dispute",
                            "The account has an open dispute; collection is paused until it is reviewed.")
        policy, policy_row = await _policy(conn)
        today = datetime.now(ZoneInfo(policy_row["timezone"])).date()
        options = payment_options(int(account["overdue_amount"]), policy, today)

        out: list[PaymentOptionOut] = []
        for option in options:
            plan_id = new_plan_id()
            await conn.execute(
                """insert into cobranza.payment_offers
                   (plan_id, tenant_id, session_token_hash, account_id, kind, installments,
                    installment_amount, last_installment_amount, total_amount, first_due_date, hardship)
                   values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                plan_id, tenant.id, token_hash, account_id, option.kind, option.installments,
                option.installment_amount, option.last_installment_amount, option.total_amount,
                option.first_due_date, option.hardship,
            )
            out.append(PaymentOptionOut(
                plan_id=plan_id,
                kind=option.kind,
                installments=option.installments,
                installment_amount=option.installment_amount,
                installment_amount_text=money_text(option.installment_amount),
                last_installment_amount=option.last_installment_amount,
                total_amount=option.total_amount,
                total_amount_text=money_text(option.total_amount),
                first_due_date=option.first_due_date,
                first_due_date_text=date_text(option.first_due_date),
                frequency=_FREQUENCY[option.kind],
                hardship=option.hardship,
            ))
        await audit(tenant.id, body.conversation_id, "get_payment_options", "ok",
                    {"offered": [o.kind for o in out]}, conn=conn)
    return PaymentOptionsResponse(
        options=[o for o in out if not o.hardship],
        hardship_option=next((o for o in out if o.hardship), None),
        note=("Amounts come from the credit policy. No discounts exist. Present the entries in options. "
              "Offer hardship_option only to customers who describe financial hardship."),
    )


@router.post("/payment-plans", response_model=PaymentPlanResponse)
async def create_payment_plan(
    body: CreatePlanRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> PaymentPlanResponse:
    _track(request, "create_payment_plan", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        existing = await conn.fetchrow(
            "select * from cobranza.payment_plans where idempotency_key = $1", body.idempotency_key
        )
        if existing is not None:
            if existing["plan_id"] != body.plan_id:
                raise ToolError(409, "idempotency_conflict",
                                "A different plan was already registered in this conversation.")
            await audit(tenant.id, body.conversation_id, "create_payment_plan", "idempotent_replay",
                        {"plan_ref": existing["plan_ref"]}, conn=conn)
            return _plan_response(existing, replay=True)

        # A plan_id is only valid if get_payment_options issued it to this same session.
        offer = await conn.fetchrow(
            """select * from cobranza.payment_offers
               where plan_id = $1 and session_token_hash = $2 and account_id = $3""",
            body.plan_id, sha256_hex(body.session_token), account_id,
        )
        if offer is None:
            raise ToolError(422, "plan_not_offered", "plan_id was not offered in this session.")

        plan_ref = new_ref(tenant.id, "P")
        plan = await conn.fetchrow(
            """insert into cobranza.payment_plans
               (plan_ref, tenant_id, account_id, plan_id, idempotency_key, installments,
                installment_amount, total_amount, first_due_date, hardship, conversation_id)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
               on conflict (tenant_id, idempotency_key) do nothing
               returning *""",
            plan_ref, tenant.id, account_id, offer["plan_id"], body.idempotency_key,
            offer["installments"], offer["installment_amount"], offer["total_amount"],
            offer["first_due_date"], offer["hardship"], body.conversation_id,
        )
        replay = plan is None
        if replay:
            plan = await conn.fetchrow(
                "select * from cobranza.payment_plans where idempotency_key = $1", body.idempotency_key
            )
        await audit(tenant.id, body.conversation_id, "create_payment_plan",
                    "idempotent_replay" if replay else "created",
                    {"plan_ref": plan["plan_ref"], "kind": offer["kind"]}, conn=conn)
    return _plan_response(plan, replay=replay)


def _plan_response(plan: asyncpg.Record, replay: bool) -> PaymentPlanResponse:
    return PaymentPlanResponse(
        plan_ref=plan["plan_ref"],
        status=plan["status"],
        installments=plan["installments"],
        installment_amount_text=money_text(plan["installment_amount"]),
        total_amount_text=money_text(plan["total_amount"]),
        first_due_date=plan["first_due_date"],
        first_due_date_text=date_text(plan["first_due_date"]),
        idempotent_replay=replay,
    )


@router.post("/payment-link", response_model=PaymentLinkResponse)
async def send_payment_link(
    body: PaymentLinkRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> PaymentLinkResponse:
    _track(request, "send_payment_link", body.conversation_id)
    settings = get_settings()
    channel = get_channel(tenant.id, tenant.channel)

    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        plan = await conn.fetchrow(
            "select * from cobranza.payment_plans where plan_ref = $1 and account_id = $2",
            body.plan_ref, account_id,
        )
        if plan is None:
            raise ToolError(404, "plan_not_found", "plan_ref does not belong to this customer.")
        recipient_row = await conn.fetchrow("select * from cobranza.recipient_for_account($1)", account_id)
        first_name = await conn.fetchval("select cobranza.first_name_for_account($1)", account_id)
        recipient = Recipient(recipient_row["phone_e164"], recipient_row["telegram_chat_id"])

        link = await conn.fetchrow("select * from cobranza.payment_links where plan_ref = $1", body.plan_ref)
        if link is not None and link["status"] in ("sent", "paid"):
            await audit(tenant.id, body.conversation_id, "send_payment_link", "idempotent_replay",
                        {"plan_ref": body.plan_ref}, conn=conn)
            return PaymentLinkResponse(sent=True, channel=link["channel"],
                                       recipient=channel.recipient_label(recipient), already_sent=True)
        if link is None:
            link = await conn.fetchrow(
                """insert into cobranza.payment_links (link_token, tenant_id, plan_ref, channel, expires_at)
                   values ($1, $2, $3, $4, now() + make_interval(hours => $5)) returning *""",
                new_link_token(), tenant.id, body.plan_ref, channel.name, settings.payment_link_ttl_hours,
            )

    amount = (f"{plan['installments']} cuotas de {money_text(plan['installment_amount'])}"
              if plan["installments"] > 1 else money_text(plan["total_amount"]))
    message = PaymentLinkMessage(
        first_name=first_name or "",
        tenant_name=tenant.name,
        plan_ref=plan["plan_ref"],
        amount_text=amount,
        due_text=date_text(plan["first_due_date"]),
        link=f"{settings.public_base_url.rstrip('/')}/pay/{link['link_token']}",
    )
    try:
        message_id = await channel.send_payment_link(recipient, message)
    except ChannelError as exc:
        async with tenant_tx(tenant.id) as conn:
            await conn.execute("update cobranza.payment_links set status = 'failed' where plan_ref = $1",
                               body.plan_ref)
            await audit(tenant.id, body.conversation_id, "send_payment_link", "channel_failed",
                        {"channel": channel.name, "error": str(exc)[:200]}, conn=conn)
        raise ToolError(502, "channel_failed", "The message could not be delivered.", audited=True)

    async with tenant_tx(tenant.id) as conn:
        await conn.execute(
            "update cobranza.payment_links set status = 'sent', message_id = $2, sent_at = now() where plan_ref = $1",
            body.plan_ref, message_id,
        )
        await audit(tenant.id, body.conversation_id, "send_payment_link", "sent",
                    {"plan_ref": body.plan_ref, "channel": channel.name}, conn=conn)
    return PaymentLinkResponse(sent=True, channel=channel.name, recipient=channel.recipient_label(recipient))


@router.post("/disputes", response_model=DisputeResponse)
async def register_dispute(
    body: DisputeRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> DisputeResponse:
    _track(request, "register_dispute", body.conversation_id)
    case_ref = new_ref(tenant.id, "D")
    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        await conn.execute(
            """insert into cobranza.disputes (case_ref, tenant_id, account_id, reason, conversation_id)
               values ($1, $2, $3, $4, $5)""",
            case_ref, tenant.id, account_id, body.reason, body.conversation_id,
        )
        await conn.execute("update cobranza.accounts set status = 'in_dispute' where id = $1", account_id)
        await audit(tenant.id, body.conversation_id, "register_dispute", "created",
                    {"case_ref": case_ref}, conn=conn)
    return DisputeResponse(
        case_ref=case_ref, status="open",
        next_step="Collection is paused. A specialist reviews the case within 5 business days and contacts the customer.",
    )


@router.post("/opt-out", response_model=OptOutResponse)
async def register_opt_out(
    body: OptOutRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> OptOutResponse:
    _track(request, "register_opt_out", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        account_ids: list[str] = []
        if account_id := await _optional_account(conn, body.session_token, body.conversation_id):
            account_ids = [account_id]
        elif body.phone_e164:
            account_ids = [r["account_id"] for r in
                           await conn.fetch("select * from cobranza.accounts_for_phone($1)", body.phone_e164)]
        phone_hash = sha256_hex(body.phone_e164) if body.phone_e164 else None
        for account_id in account_ids or [None]:
            await conn.execute(
                """insert into cobranza.contacts
                   (tenant_id, account_id, phone_hash, channel, direction, result, opt_out, conversation_id)
                   values ($1, $2, $3, 'voice', 'inbound', 'opt_out_requested', true, $4)""",
                tenant.id, account_id, phone_hash, body.conversation_id,
            )
        await audit(tenant.id, body.conversation_id, "register_opt_out", "registered",
                    {"linked_accounts": len(account_ids)}, conn=conn)
    if account_ids:
        message = f"Opt-out applied. {tenant.name} will not contact the customer for collections again."
    else:
        message = ("Opt-out request recorded, but it could not be linked to an account because identity "
                   "is not verified. Offer to verify identity so it applies to the account.")
    return OptOutResponse(registered=True, linked_to_account=bool(account_ids), message=message)


@router.post("/callbacks", response_model=CallbackResponse)
async def request_callback(
    body: CallbackRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> CallbackResponse:
    _track(request, "request_callback", body.conversation_id)
    callback_ref = new_ref(tenant.id, "C")
    async with tenant_tx(tenant.id) as conn:
        account_id = await _optional_account(conn, body.session_token, body.conversation_id)
        await conn.execute(
            """insert into cobranza.callbacks
               (callback_ref, tenant_id, account_id, reason, preferred_window, conversation_id)
               values ($1, $2, $3, $4, $5, $6)""",
            callback_ref, tenant.id, account_id, body.reason, body.preferred_window, body.conversation_id,
        )
        await audit(tenant.id, body.conversation_id, "request_callback", "created",
                    {"callback_ref": callback_ref, "linked": account_id is not None}, conn=conn)
    return CallbackResponse(
        callback_ref=callback_ref,
        next_step=(f"An advisor will call back {body.preferred_window}, within legal contact hours "
                   "(Monday to Friday 7 a.m. to 7 p.m., Saturday 8 a.m. to 3 p.m.)."),
    )
