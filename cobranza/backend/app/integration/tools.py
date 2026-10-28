"""Webhook tools called by the ElevenLabs agent. Everything with consequences
(identity, money, compliance) is decided here; the agent only receives masked data."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.db import tenant_tx
from app.fintech_sim.offer_math import monthly_payment, total_cost
from app.fintech_sim.policy import PaymentOptionsResult, PlanOption, ProductPolicyRow, parse_product_policy, payment_options_for_account
from app.integration.auth import Tenant, ToolError, audit, current_tenant
from app.integration.channels import ChannelError, PaymentLinkMessage, Recipient, get_channel
from app.integration.formatting import date_text, money_text
from app.integration.schemas import (
    AccountSummaryResponse,
    CallbackRequest,
    CallbackResponse,
    ConfirmDisbursementRequest,
    ConfirmDisbursementResponse,
    CreatePlanRequest,
    CreditOfferResponse,
    DisbursementOtpResponse,
    DisputeRequest,
    DisputeResponse,
    OptOutRequest,
    OptOutResponse,
    PaymentLinkRequest,
    PaymentLinkResponse,
    PaymentOptionOut,
    PaymentOptionsRequest,
    PaymentOptionsResponse,
    PaymentPlanResponse,
    SessionRequest,
    SimulateOfferRequest,
    SimulateOfferResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from app.integration.security import (
    new_link_token,
    new_offer_id,
    new_otp_code,
    new_plan_id,
    new_ref,
    new_session_token,
    sha256_hex,
)

router = APIRouter(prefix="/tools", tags=["tools"])

_FREQUENCY = {
    "full": "pago único",
    "installments": "mensual",
    "hardship": "mensual",
    "minimum": "pago único",
    "refinance": "mensual",
    "promise": "pago único",
}


def _track(request: Request, tool: str, conversation_id: str) -> None:
    request.state.tool = tool
    request.state.conversation_id = conversation_id


async def _default_product_policy(conn: asyncpg.Connection) -> ProductPolicyRow:
    row = await conn.fetchrow("select policy from cobranza.product_policies limit 1")
    if row is None:
        raise ToolError(500, "policy_missing", "Tenant has no credit policy configured.")
    return parse_product_policy(row["policy"])


async def _product_policy(conn: asyncpg.Connection, product_code: str) -> ProductPolicyRow:
    row = await conn.fetchrow(
        "select policy from cobranza.product_policies where product_code = $1", product_code
    )
    if row is None:
        raise ToolError(500, "policy_missing", f"No policy for product {product_code}.")
    return parse_product_policy(row["policy"])


def _option_out(option: PlanOption, plan_id: str) -> PaymentOptionOut:
    return PaymentOptionOut(
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
        frequency=_FREQUENCY.get(option.kind, "mensual"),
        hardship=option.hardship,
    )


async def _persist_options(
    conn: asyncpg.Connection,
    tenant_id: str,
    token_hash: str,
    account_id: str,
    options: list[PlanOption],
) -> list[PaymentOptionOut]:
    out: list[PaymentOptionOut] = []
    for option in options:
        plan_id = new_plan_id()
        await conn.execute(
            """insert into cobranza.payment_offers
               (plan_id, tenant_id, session_token_hash, account_id, kind, installments,
                installment_amount, last_installment_amount, total_amount, first_due_date, hardship)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            plan_id, tenant_id, token_hash, account_id, option.kind, option.installments,
            option.installment_amount, option.last_installment_amount, option.total_amount,
            option.first_due_date, option.hardship,
        )
        out.append(_option_out(option, plan_id))
    return out


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
        policy_row = await _default_product_policy(conn)
        max_attempts = policy_row.max_verification_attempts
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
            policy_row.session_ttl_minutes,
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
        product_policy = await _product_policy(conn, account["product_code"])
        await audit(tenant.id, body.conversation_id, "get_account_summary", "ok", conn=conn)
        overdue, total = int(account["overdue_amount"]), int(account["total_balance"])
        mode = product_policy.options.get("mode", "overdue")
        dpd = int(account["days_past_due"])
        min_pay = int(account["minimum_payment"] or 0)
        due = account["due_date"]
        return AccountSummaryResponse(
            account=f"terminada en {account['account_last4']}",
            account_last4=account["account_last4"],
            product=account["product"],
            overdue_amount=overdue,
            overdue_amount_text=money_text(overdue),
            total_balance=total,
            total_balance_text=money_text(total),
            days_past_due=None if mode == "card_preventive" and dpd == 0 else dpd,
            minimum_payment=min_pay if mode == "card_preventive" else None,
            minimum_payment_text=money_text(min_pay) if mode == "card_preventive" and min_pay > 0 else None,
            due_date=due if mode == "card_preventive" else None,
            due_date_text=date_text(due) if mode == "card_preventive" and due else None,
            status=account["status"],
        )


@router.post("/payment-options", response_model=PaymentOptionsResponse)
async def get_payment_options(
    body: PaymentOptionsRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> PaymentOptionsResponse:
    _track(request, "get_payment_options", body.conversation_id)
    token_hash = sha256_hex(body.session_token)
    promise_date: date | None = None
    if body.promise_date:
        try:
            promise_date = date.fromisoformat(body.promise_date)
        except ValueError as exc:
            raise ToolError(422, "invalid_promise_date", "promise_date must be YYYY-MM-DD.") from exc
    async with tenant_tx(tenant.id) as conn:
        account_id = await _session_account(conn, body.session_token)
        account = await conn.fetchrow("select * from cobranza.accounts where id = $1", account_id)
        if account["status"] == "in_dispute":
            raise ToolError(409, "account_in_dispute",
                            "The account has an open dispute; collection is paused until it is reviewed.")
        product_policy = await _product_policy(conn, account["product_code"])
        today = datetime.now(ZoneInfo(product_policy.timezone)).date()
        mode = product_policy.options.get("mode", "overdue")
        try:
            computed = payment_options_for_account(
                mode=mode,
                overdue_amount=int(account["overdue_amount"]),
                total_balance=int(account["total_balance"]),
                minimum_payment=int(account["minimum_payment"] or 0),
                days_past_due=int(account["days_past_due"]),
                policy_opts=product_policy.options,
                today=today,
                promise_date=promise_date,
            )
        except ValueError as exc:
            if str(exc) == "promise_outside_window":
                raise ToolError(422, "promise_outside_window",
                                "Promise date must be within the next 7 days.") from exc
            raise
        if computed.escalate:
            await audit(tenant.id, body.conversation_id, "get_payment_options", "escalate", conn=conn)
            return PaymentOptionsResponse(
                options=[], hardship_option=None, refinance_options=[], promise_option=None,
                escalate=True,
                note="This case must be handled by an advisor; do not negotiate further options.",
            )

        main_out = await _persist_options(conn, tenant.id, token_hash, account_id, computed.options)
        hardship_out = None
        if computed.hardship_option:
            hardship_out = (await _persist_options(
                conn, tenant.id, token_hash, account_id, [computed.hardship_option]))[0]
        refinance_out = await _persist_options(
            conn, tenant.id, token_hash, account_id, computed.refinance_options)
        promise_out = None
        if computed.promise_option:
            promise_out = (await _persist_options(
                conn, tenant.id, token_hash, account_id, [computed.promise_option]))[0]
        await audit(tenant.id, body.conversation_id, "get_payment_options", "ok",
                    {"offered": [o.kind for o in main_out]}, conn=conn)
        note = ("Amounts come from the credit policy. No discounts exist. Present the entries in options. "
                "Offer hardship_option only to customers who describe financial hardship.")
        if mode == "card_preventive":
            note = ("Amounts come from the credit policy. Offer refinance_options only if the customer "
                    "says they cannot pay the minimum or total.")
        if mode == "promise":
            note = "Offer promise_option only after the customer chooses a date within the next 7 days."
        return PaymentOptionsResponse(
            options=main_out,
            hardship_option=hardship_out,
            refinance_options=refinance_out,
            promise_option=promise_out,
            note=note,
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
                   (tenant_id, account_id, phone_hash, channel, direction, result, opt_out, conversation_id, purpose)
                   values ($1, $2, $3, 'voice', 'inbound', 'opt_out_requested', true, $4, $5)""",
                tenant.id, account_id, phone_hash, body.conversation_id, body.purpose,
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


async def _person_for_session(conn: asyncpg.Connection, token: str) -> tuple[str, str]:
    account_id = await _session_account(conn, token)
    row = await conn.fetchrow("select person_token, product_code from cobranza.accounts where id = $1", account_id)
    return row["person_token"], account_id


@router.post("/credit-offer", response_model=CreditOfferResponse)
async def get_credit_offer(
    body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> CreditOfferResponse:
    _track(request, "get_credit_offer", body.conversation_id)
    token_hash = sha256_hex(body.session_token)
    async with tenant_tx(tenant.id) as conn:
        person_token, _ = await _person_for_session(conn, body.session_token)
        delinquent = await conn.fetchrow(
            """select product_code from cobranza.accounts
               where person_token = $1 and (days_past_due > 0 or status = 'in_dispute') limit 1""",
            person_token,
        )
        if delinquent:
            await audit(tenant.id, body.conversation_id, "get_credit_offer", "blocked_delinquency", conn=conn)
            return CreditOfferResponse(
                available=False,
                delinquent_product_code=delinquent["product_code"],
                message="Customer has delinquency; do not offer credit.",
            )
        offer = await conn.fetchrow(
            """select * from cobranza.credit_offers
               where person_token = $1 and status = 'offered' and expires_at > now()
               order by created_at desc limit 1""",
            person_token,
        )
        if offer is None:
            await audit(tenant.id, body.conversation_id, "get_credit_offer", "empty", conn=conn)
            return CreditOfferResponse(available=False, message="No active offer for this customer.")
        await conn.execute(
            """update cobranza.credit_offers
               set session_token_hash = $2, conversation_id = $3
               where offer_id = $1""",
            offer["offer_id"], token_hash, body.conversation_id,
        )
        rate = float(offer["rate_ea"])
        await audit(tenant.id, body.conversation_id, "get_credit_offer", "ok",
                    {"offer_id": offer["offer_id"]}, conn=conn)
    amount = int(offer["amount"])
    return CreditOfferResponse(
        available=True,
        offer_id=offer["offer_id"],
        amount=amount,
        amount_text=money_text(amount),
        rate_ea_text=f"{rate:.2f} por ciento efectivo anual",
        available_terms=list(offer["available_terms"]),
        message="Offer loaded from the bank; amounts cannot be changed.",
    )


@router.post("/simulate-offer", response_model=SimulateOfferResponse)
async def simulate_offer(
    body: SimulateOfferRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> SimulateOfferResponse:
    _track(request, "simulate_offer", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        token_hash = sha256_hex(body.session_token)
        offer = await conn.fetchrow(
            """select * from cobranza.credit_offers
               where offer_id = $1 and session_token_hash = $2 and status = 'offered'""",
            body.offer_id, token_hash,
        )
        if offer is None:
            raise ToolError(422, "offer_not_in_session", "offer_id is not active for this session.")
        if body.term_months not in offer["available_terms"]:
            raise ToolError(422, "term_not_allowed", "term_months is not in available_terms.")
        amount = int(offer["amount"])
        rate = float(offer["rate_ea"])
        installment = monthly_payment(amount, rate, body.term_months)
        total = total_cost(installment, body.term_months)
        rate_text = f"{rate:.2f} por ciento efectivo anual"
        spoken = (
            f"Con un plazo de {body.term_months} meses, la cuota mensual sería de {money_text(installment)}, "
            f"con una tasa de {rate_text}. El costo total del crédito sería de {money_text(total)}."
        )
        await audit(tenant.id, body.conversation_id, "simulate_offer", "ok",
                    {"offer_id": body.offer_id, "term": body.term_months}, conn=conn)
    return SimulateOfferResponse(
        term_months=body.term_months,
        installment_amount=installment,
        installment_amount_text=money_text(installment),
        rate_ea_text=rate_text,
        total_cost_text=money_text(total),
        spoken_summary=spoken,
    )


@router.post("/disbursement-otp", response_model=DisbursementOtpResponse)
async def request_disbursement_otp(
    body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> DisbursementOtpResponse:
    _track(request, "request_disbursement_otp", body.conversation_id)
    settings = get_settings()
    channel_impl = get_channel(tenant.id, tenant.channel)
    async with tenant_tx(tenant.id) as conn:
        person_token, account_id = await _person_for_session(conn, body.session_token)
        token_hash = sha256_hex(body.session_token)
        offer = await conn.fetchrow(
            """select * from cobranza.credit_offers
               where person_token = $1 and session_token_hash = $2 and status = 'offered'""",
            person_token, token_hash,
        )
        if offer is None:
            raise ToolError(422, "offer_not_in_session", "No offer linked to this session.")
        if offer["status"] == "locked":
            raise ToolError(409, "offer_locked", "Too many failed OTP attempts.")
        existing = await conn.fetchrow("select * from cobranza.disbursement_otps where offer_id = $1", offer["offer_id"])
        if existing and existing["attempts"] >= 3:
            await conn.execute("update cobranza.credit_offers set status = 'locked' where offer_id = $1",
                               offer["offer_id"])
            raise ToolError(409, "offer_locked", "Too many failed OTP attempts.")
        code = new_otp_code()
        await conn.execute(
            """insert into cobranza.disbursement_otps (offer_id, tenant_id, code_hash, expires_at)
               values ($1, $2, $3, now() + interval '15 minutes')
               on conflict (offer_id) do update set code_hash = excluded.code_hash,
                 expires_at = excluded.expires_at, attempts = 0""",
            offer["offer_id"], tenant.id, sha256_hex(code),
        )
        recipient_row = await conn.fetchrow("select * from cobranza.recipient_for_account($1)", account_id)
        recipient = Recipient(recipient_row["phone_e164"], recipient_row["telegram_chat_id"])
    text = f"{tenant.name}: tu código de un solo uso para confirmar el desembolso es {code}. Válido por 15 minutos."
    try:
        if hasattr(channel_impl, "send_text"):
            await channel_impl.send_text(recipient, text)
        else:
            raise ChannelError("channel cannot send OTP")
    except ChannelError as exc:
        raise ToolError(502, "channel_failed", str(exc)) from exc
    async with tenant_tx(tenant.id) as conn:
        await audit(tenant.id, body.conversation_id, "request_disbursement_otp", "sent", conn=conn)
    return DisbursementOtpResponse(
        sent=True, channel=tenant.channel,
        message="OTP sent on Telegram. Never read the code back to the customer.",
    )


@router.post("/confirm-disbursement", response_model=ConfirmDisbursementResponse)
async def confirm_disbursement(
    body: ConfirmDisbursementRequest, request: Request, tenant: Tenant = Depends(current_tenant)
) -> ConfirmDisbursementResponse:
    _track(request, "confirm_disbursement", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        token_hash = sha256_hex(body.session_token)
        offer = await conn.fetchrow(
            """select * from cobranza.credit_offers
               where offer_id = $1 and session_token_hash = $2""",
            body.offer_id, token_hash,
        )
        if offer is None:
            raise ToolError(422, "offer_not_in_session", "offer_id is not active for this session.")
        if offer["status"] == "disbursed" and offer["disbursement_ref"]:
            await audit(tenant.id, body.conversation_id, "confirm_disbursement", "idempotent_replay", conn=conn)
            return ConfirmDisbursementResponse(
                confirmed=True,
                disbursement_ref=offer["disbursement_ref"],
                amount_text=money_text(int(offer["amount"])),
                idempotent_replay=True,
                message="Disbursement was already confirmed.",
            )
        if offer["status"] == "locked":
            raise ToolError(409, "offer_locked", "Offer is locked after failed OTP attempts.")
        otp_row = await conn.fetchrow("select * from cobranza.disbursement_otps where offer_id = $1", body.offer_id)
        if otp_row is None:
            raise ToolError(422, "otp_missing", "Request an OTP first.")
        expires = otp_row["expires_at"]
        now_db = await conn.fetchval("select now()")
        if expires <= now_db:
            raise ToolError(422, "otp_expired", "OTP expired; request a new one.")
        if otp_row["attempts"] >= 3:
            await conn.execute("update cobranza.credit_offers set status = 'locked' where offer_id = $1", body.offer_id)
            raise ToolError(409, "offer_locked", "Too many failed OTP attempts.")
        if sha256_hex(body.otp_code) != otp_row["code_hash"]:
            attempts = otp_row["attempts"] + 1
            await conn.execute("update cobranza.disbursement_otps set attempts = $2 where offer_id = $1",
                               body.offer_id, attempts)
            if attempts >= 3:
                await conn.execute("update cobranza.credit_offers set status = 'locked' where offer_id = $1",
                                   body.offer_id)
                raise ToolError(409, "offer_locked", "Too many failed OTP attempts.")
            raise ToolError(422, "otp_invalid", "Incorrect OTP.")
        ref = offer["disbursement_ref"] or new_ref(tenant.id, "S")
        await conn.execute(
            """update cobranza.credit_offers
               set status = 'disbursed', disbursement_ref = $2 where offer_id = $1""",
            body.offer_id, ref,
        )
        await audit(tenant.id, body.conversation_id, "confirm_disbursement", "confirmed",
                    {"disbursement_ref": ref}, conn=conn)
        return ConfirmDisbursementResponse(
            confirmed=True,
            disbursement_ref=ref,
            amount_text=money_text(int(offer["amount"])),
            message="Disbursement confirmed.",
        )
