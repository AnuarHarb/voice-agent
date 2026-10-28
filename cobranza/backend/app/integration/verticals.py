"""Webhook tools for the Inmercity demo agents (salud, retail, telco, inmobiliaria).

Same contract as the collections tools: the agent talks, this code decides. Identity is checked
here, policies (cancellation window, return window, consent, retention discounts) live here, and
the agent only receives short, speakable results. Everything runs in the `demos` tenant."""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StringConstraints

from app.db import tenant_tx
from app.integration.auth import Tenant, ToolError, audit, current_tenant
from app.integration.formatting import date_text, money_text
from app.integration.schemas import (
    OptionalSessionToken,
    SessionRequest,
    ToolRequest,
    VerifyIdentityRequest,
)
from app.integration.security import new_ref, new_session_token, sha256_hex

router = APIRouter(prefix="/verticals", tags=["verticals"])

DEMO_TENANT = "demos"
TZ = ZoneInfo("America/Bogota")
MAX_ATTEMPTS = 3
SESSION_MINUTES = 30
CANCEL_WINDOW_HOURS = 24
RETURN_WINDOW_DAYS = 30
CANCELLATION_NOTICE_DAYS = 30

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Vertical = Literal["salud", "retail", "telco"]


# ---------- request models ----------

class VerifyCustomerRequest(VerifyIdentityRequest):
    vertical: Vertical


class AvailabilityRequest(SessionRequest):
    specialty: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""


class BookAppointmentRequest(SessionRequest):
    slot_id: Annotated[str, StringConstraints(min_length=5, max_length=64)]
    replaces_ref: Annotated[str, StringConstraints(max_length=32)] = ""


class AppointmentRefRequest(SessionRequest):
    appointment_ref: Annotated[str, StringConstraints(min_length=5, max_length=32)]


class OrderRequest(SessionRequest):
    order_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] = ""


class ReturnRequest(SessionRequest):
    order_no: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=32)]
    reason: Reason


class OfferReasonRequest(SessionRequest):
    reason: Literal["precio", "falla", "necesidad"]


class IssueRequest(SessionRequest):
    issue: Reason


class AcceptOfferRequest(SessionRequest):
    offer_id: Annotated[str, StringConstraints(min_length=5, max_length=32)]


class CancelServiceRequest(SessionRequest):
    reason: Reason


class HandoffRequest(ToolRequest):
    session_token: OptionalSessionToken = ""
    reason: Reason


class PropertySearchRequest(ToolRequest):
    zone: Short = ""
    kind: Literal["venta", "arriendo", ""] = ""
    bedrooms: Annotated[int, Field(ge=0, le=10)] = 0
    max_price: Annotated[int, Field(ge=0, le=100_000_000_000)] = 0


class SaveLeadRequest(ToolRequest):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    zone: Short = ""
    budget: Annotated[int, Field(ge=0, le=100_000_000_000)] = 0
    bedrooms: Annotated[int, Field(ge=0, le=10)] = 0
    timeline: Literal["inmediato", "1-3 meses", "3-6 meses", "explorando"]


class LeadSlotsRequest(ToolRequest):
    pass


class BookAdvisorRequest(ToolRequest):
    slot_id: Annotated[str, StringConstraints(min_length=5, max_length=64)]


# ---------- helpers ----------

def _demo_only(tenant: Tenant) -> None:
    if tenant.id != DEMO_TENANT:
        raise ToolError(403, "wrong_tenant", "These tools belong to the demos tenant.")


def _track(request: Request, tool: str, conversation_id: str) -> None:
    request.state.tool = tool
    request.state.conversation_id = conversation_id


def _slot_text(starts_at: datetime) -> str:
    local = starts_at.astimezone(TZ)
    hour = local.hour % 12 or 12
    suffix = "de la mañana" if local.hour < 12 else "de la tarde"
    return f"{date_text(local.date())} a las {hour} {suffix}"


async def _customer(conn: asyncpg.Connection, token: str, vertical: str) -> asyncpg.Record:
    """Account tools only work with a live token issued by verify_customer for this tenant."""
    row = await conn.fetchrow(
        """select c.id, c.consent_commercial
           from cobranza.vertical_sessions s
           join cobranza.vertical_customers c on c.id = s.customer_id
           where s.token_hash = $1 and s.expires_at > now() and c.vertical = $2""",
        sha256_hex(token), vertical,
    )
    if row is None:
        raise ToolError(401, "invalid_session", "Identity is not verified for this conversation.")
    return row


# ---------- identity and handoff ----------

@router.post("/verify-customer")
async def verify_customer(body: VerifyCustomerRequest, request: Request,
                          tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "verify_customer", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        failures = await conn.fetchval(
            """select count(*) from cobranza.audit_log
               where tool = 'verify_customer' and result = 'not_verified'
                 and conversation_id = $1 and created_at > now() - interval '1 hour'""",
            body.conversation_id,
        )
        if failures >= MAX_ATTEMPTS:
            await audit(tenant.id, body.conversation_id, "verify_customer", "locked", conn=conn)
            return {"verified": False, "session_token": "", "attempts_remaining": 0, "locked": True,
                    "incomplete": False, "customer_first_name": "",
                    "message": "Too many failed attempts. Offer a handoff to a human advisor."}

        last4, born = body.parsed()
        if last4 is None or born is None:
            await audit(tenant.id, body.conversation_id, "verify_customer", "incomplete", conn=conn)
            return {"verified": False, "session_token": "", "attempts_remaining": MAX_ATTEMPTS - failures,
                    "locked": False, "incomplete": True, "customer_first_name": "",
                    "message": "Missing or unreadable data. Ask for the last four digits of the cédula "
                               "and the birth date with day, month and year."}

        matches = await conn.fetch(
            "select * from cobranza.match_vertical_customer($1, $2, $3)", body.vertical, last4, born)
        if len(matches) != 1:
            await audit(tenant.id, body.conversation_id, "verify_customer", "not_verified", conn=conn)
            remaining = max(MAX_ATTEMPTS - failures - 1, 0)
            return {"verified": False, "session_token": "", "attempts_remaining": remaining,
                    "locked": remaining == 0, "incomplete": False, "customer_first_name": "",
                    "message": "The data does not match. Do not reveal whether a customer exists."}

        token = new_session_token()
        await conn.execute(
            """insert into cobranza.vertical_sessions (token_hash, tenant_id, customer_id, conversation_id, expires_at)
               values ($1, $2, $3, $4, now() + make_interval(mins => $5))""",
            sha256_hex(token), tenant.id, matches[0]["customer_id"], body.conversation_id, SESSION_MINUTES,
        )
        await audit(tenant.id, body.conversation_id, "verify_customer", "verified", conn=conn)
    return {"verified": True, "session_token": token, "attempts_remaining": MAX_ATTEMPTS - failures,
            "locked": False, "incomplete": False, "customer_first_name": matches[0]["first_name"],
            "message": "Identity verified."}


@router.post("/handoff")
async def handoff(body: HandoffRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "handoff_to_human", body.conversation_id)
    ref = new_ref(tenant.id, "H")
    async with tenant_tx(tenant.id) as conn:
        customer_id = None
        if body.session_token:
            customer_id = await conn.fetchval(
                "select customer_id from cobranza.vertical_sessions where token_hash = $1 and expires_at > now()",
                sha256_hex(body.session_token),
            )
        await conn.execute(
            "insert into cobranza.handoffs (ref, tenant_id, customer_id, conversation_id, reason) values ($1, $2, $3, $4, $5)",
            ref, tenant.id, customer_id, body.conversation_id, body.reason,
        )
        await audit(tenant.id, body.conversation_id, "handoff_to_human", "ok", conn=conn)
    return {"ok": True, "handoff_ref": ref,
            "message": "A human advisor will contact the customer. Give the reference and close politely."}


# ---------- salud: citas ----------

@router.post("/salud/availability")
async def availability(body: AvailabilityRequest, request: Request,
                       tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "list_availability", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        await _customer(conn, body.session_token, "salud")
        await conn.execute("select cobranza.ensure_demo_slots()")
        rows = await conn.fetch(
            """select sl.id, sl.starts_at, sp.name, sp.specialty
               from cobranza.clinic_slots sl join cobranza.clinic_specialists sp on sp.id = sl.specialist_id
               where not sl.taken and sl.starts_at > now() + interval '2 hours'
                 and ($1 = '' or sp.specialty ilike '%' || $1 || '%')
               order by sl.starts_at limit 4""",
            body.specialty,
        )
        await audit(tenant.id, body.conversation_id, "list_availability", "ok", conn=conn)
    return {"slots": [{"slot_id": r["id"], "specialist": r["name"], "specialty": r["specialty"],
                       "when_text": _slot_text(r["starts_at"])} for r in rows],
            "message": "" if rows else "No availability for that specialty in the next days."}


@router.post("/salud/my-appointment")
async def my_appointment(body: SessionRequest, request: Request,
                         tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "get_my_appointment", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "salud")
        row = await conn.fetchrow(
            """select a.ref, sl.starts_at, sp.name, sp.specialty
               from cobranza.appointments a
               join cobranza.clinic_slots sl on sl.id = a.slot_id
               join cobranza.clinic_specialists sp on sp.id = sl.specialist_id
               where a.customer_id = $1 and a.status = 'booked' and sl.starts_at > now()
               order by sl.starts_at limit 1""",
            customer["id"],
        )
        await audit(tenant.id, body.conversation_id, "get_my_appointment", "ok", conn=conn)
    if row is None:
        return {"has_appointment": False, "message": "The customer has no upcoming appointment."}
    return {"has_appointment": True, "appointment_ref": row["ref"], "specialist": row["name"],
            "specialty": row["specialty"], "when_text": _slot_text(row["starts_at"]),
            "message": "Upcoming appointment found."}


@router.post("/salud/book")
async def book_appointment(body: BookAppointmentRequest, request: Request,
                           tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "book_appointment", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "salud")
        # Atomic claim: two conversations can never take the same slot.
        slot = await conn.fetchrow(
            """update cobranza.clinic_slots set taken = true
               where id = $1 and not taken and starts_at > now() returning id, starts_at, specialist_id""",
            body.slot_id,
        )
        if slot is None:
            await audit(tenant.id, body.conversation_id, "book_appointment", "slot_unavailable", conn=conn)
            return {"booked": False, "message": "That slot is no longer available. Offer other options."}
        if body.replaces_ref:
            old = await conn.fetchrow(
                """update cobranza.appointments set status = 'cancelled'
                   where ref = $1 and customer_id = $2 and status = 'booked' returning slot_id""",
                body.replaces_ref, customer["id"],
            )
            if old:
                await conn.execute("update cobranza.clinic_slots set taken = false where id = $1", old["slot_id"])
        ref = new_ref(tenant.id, "C")
        await conn.execute(
            "insert into cobranza.appointments (ref, tenant_id, customer_id, slot_id) values ($1, $2, $3, $4)",
            ref, tenant.id, customer["id"], slot["id"],
        )
        specialist = await conn.fetchval("select name from cobranza.clinic_specialists where id = $1",
                                         slot["specialist_id"])
        await audit(tenant.id, body.conversation_id, "book_appointment", "ok", conn=conn)
    return {"booked": True, "appointment_ref": ref, "specialist": specialist,
            "when_text": _slot_text(slot["starts_at"]), "message": "Appointment booked."}


@router.post("/salud/cancel")
async def cancel_appointment(body: AppointmentRefRequest, request: Request,
                             tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "cancel_appointment", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "salud")
        row = await conn.fetchrow(
            """select a.slot_id, sl.starts_at from cobranza.appointments a
               join cobranza.clinic_slots sl on sl.id = a.slot_id
               where a.ref = $1 and a.customer_id = $2 and a.status = 'booked'""",
            body.appointment_ref, customer["id"],
        )
        if row is None:
            return {"cancelled": False, "message": "No active appointment with that reference."}
        if row["starts_at"] - datetime.now(tz=row["starts_at"].tzinfo) < timedelta(hours=CANCEL_WINDOW_HOURS):
            await audit(tenant.id, body.conversation_id, "cancel_appointment", "too_late", conn=conn)
            return {"cancelled": False, "too_late": True,
                    "message": f"Cancellations need {CANCEL_WINDOW_HOURS} hours of notice. Offer to reschedule or a human handoff."}
        await conn.execute("update cobranza.appointments set status = 'cancelled' where ref = $1", body.appointment_ref)
        await conn.execute("update cobranza.clinic_slots set taken = false where id = $1", row["slot_id"])
        await audit(tenant.id, body.conversation_id, "cancel_appointment", "ok", conn=conn)
    return {"cancelled": True, "message": "Appointment cancelled."}


@router.post("/salud/reminder")
async def send_reminder(body: AppointmentRefRequest, request: Request,
                        tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "send_reminder", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "salud")
        exists = await conn.fetchval(
            "select 1 from cobranza.appointments where ref = $1 and customer_id = $2 and status = 'booked'",
            body.appointment_ref, customer["id"],
        )
        if not exists:
            return {"sent": False, "message": "No active appointment with that reference."}
        await conn.execute(
            "insert into cobranza.notifications (tenant_id, customer_id, kind, reference) values ($1, $2, 'appointment_reminder', $3)",
            tenant.id, customer["id"], body.appointment_ref,
        )
        await audit(tenant.id, body.conversation_id, "send_reminder", "ok", conn=conn)
    return {"sent": True, "message": "Reminder queued (simulated in the demo)."}


# ---------- retail: pedidos y carritos ----------

_ORDER_STATUS = {
    "preparing": "se está preparando",
    "shipped": "ya fue despachado",
    "out_for_delivery": "va en camino y llega hoy",
    "delivered": "ya fue entregado",
}


def _order_view(row: asyncpg.Record) -> dict:
    out = {"order_no": row["order_no"], "status": row["status"], "status_text": _ORDER_STATUS[row["status"]],
           "carrier": row["carrier"] or "", "items": row["items"], "total_text": money_text(row["total"])}
    if row["eta_offset_days"] is not None and row["status"] != "delivered":
        out["eta_text"] = date_text(date.today() + timedelta(days=row["eta_offset_days"]))
    if row["delivered_days_ago"] is not None:
        out["delivered_days_ago"] = row["delivered_days_ago"]
    return out


@router.post("/retail/order-status")
async def order_status(body: OrderRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "get_order_status", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "retail")
        rows = await conn.fetch(
            """select * from cobranza.orders where customer_id = $1 and ($2 = '' or order_no = $2)
               order by order_no desc limit 3""",
            customer["id"], body.order_no.upper(),
        )
        await audit(tenant.id, body.conversation_id, "get_order_status", "ok", conn=conn)
    return {"orders": [_order_view(r) for r in rows],
            "message": "" if rows else "No orders found for this customer."}


@router.post("/retail/return")
async def start_return(body: ReturnRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "start_return", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "retail")
        order = await conn.fetchrow(
            "select * from cobranza.orders where order_no = $1 and customer_id = $2",
            body.order_no.upper(), customer["id"],
        )
        if order is None:
            return {"started": False, "message": "No order with that number for this customer."}
        if order["status"] != "delivered":
            await audit(tenant.id, body.conversation_id, "start_return", "not_delivered", conn=conn)
            return {"started": False, "message": "Only delivered orders can be returned. Explain the order status instead."}
        if (order["delivered_days_ago"] or 0) > RETURN_WINDOW_DAYS:
            await audit(tenant.id, body.conversation_id, "start_return", "outside_window", conn=conn)
            return {"started": False, "outside_window": True,
                    "message": f"Returns are accepted up to {RETURN_WINDOW_DAYS} days after delivery. Offer a human handoff."}
        ref = new_ref(tenant.id, "D")
        await conn.execute(
            "insert into cobranza.order_returns (ref, tenant_id, order_no, reason) values ($1, $2, $3, $4)",
            ref, tenant.id, order["order_no"], body.reason,
        )
        await conn.execute(
            "insert into cobranza.notifications (tenant_id, customer_id, kind, reference) values ($1, $2, 'return_label', $3)",
            tenant.id, customer["id"], ref,
        )
        await audit(tenant.id, body.conversation_id, "start_return", "ok", conn=conn)
    return {"started": True, "return_ref": ref, "message": "Return created. The label is sent by message (simulated)."}


@router.post("/retail/cart")
async def get_cart(body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "get_cart", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "retail")
        cart = await conn.fetchrow(
            "select * from cobranza.carts where customer_id = $1 and status in ('open', 'link_sent') limit 1",
            customer["id"],
        )
        await audit(tenant.id, body.conversation_id, "get_cart", "ok", conn=conn)
    if cart is None:
        return {"has_cart": False, "message": "The customer has no pending cart."}
    return {"has_cart": True, "items": cart["items"], "total_text": money_text(cart["total"]),
            "commercial_consent": customer["consent_commercial"], "message": "Pending cart found."}


@router.post("/retail/checkout-link")
async def send_checkout_link(body: SessionRequest, request: Request,
                             tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "send_checkout_link", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "retail")
        if not customer["consent_commercial"]:
            await audit(tenant.id, body.conversation_id, "send_checkout_link", "no_consent", conn=conn)
            return {"sent": False, "no_consent": True,
                    "message": "The customer has no commercial consent. Do not send anything; close politely."}
        cart = await conn.fetchrow(
            "select id from cobranza.carts where customer_id = $1 and status in ('open', 'link_sent') limit 1",
            customer["id"],
        )
        if cart is None:
            return {"sent": False, "message": "No pending cart."}
        await conn.execute("update cobranza.carts set status = 'link_sent' where id = $1", cart["id"])
        await conn.execute(
            "insert into cobranza.notifications (tenant_id, customer_id, kind, reference) values ($1, $2, 'checkout_link', $3)",
            tenant.id, customer["id"], cart["id"],
        )
        await audit(tenant.id, body.conversation_id, "send_checkout_link", "ok", conn=conn)
    return {"sent": True, "message": "Checkout link sent by message (simulated)."}


# ---------- telco: soporte y retención ----------

@router.post("/telco/outage")
async def check_outage(body: SessionRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "check_outage", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        row = await conn.fetchrow(
            """select o.active, o.description, s.area from cobranza.telco_services s
               join cobranza.telco_outages o on o.area = s.area and o.tenant_id = s.tenant_id
               where s.customer_id = $1""",
            customer["id"],
        )
        await audit(tenant.id, body.conversation_id, "check_outage", "ok", conn=conn)
    if row is None:
        return {"outage": False, "area": "", "message": "No service found for this customer."}
    return {"outage": row["active"], "area": row["area"], "message": row["description"]}


@router.post("/telco/diagnostic")
async def run_diagnostic(body: SessionRequest, request: Request,
                         tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "run_diagnostic", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        svc = await conn.fetchrow("select plan, modem_state from cobranza.telco_services where customer_id = $1",
                                  customer["id"])
        await audit(tenant.id, body.conversation_id, "run_diagnostic", "ok", conn=conn)
    if svc is None:
        return {"healthy": False, "message": "No service found for this customer."}
    if svc["modem_state"] == "unresponsive":
        return {"healthy": False, "plan": svc["plan"],
                "message": "The modem does not respond remotely. A technical visit is needed; open a ticket."}
    return {"healthy": True, "plan": svc["plan"], "message": "The line and the modem respond normally."}


@router.post("/telco/ticket")
async def open_ticket(body: IssueRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "open_ticket", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        ref = new_ref(tenant.id, "T")
        await conn.execute(
            "insert into cobranza.telco_tickets (ref, tenant_id, customer_id, issue) values ($1, $2, $3, $4)",
            ref, tenant.id, customer["id"], body.issue,
        )
        await audit(tenant.id, body.conversation_id, "open_ticket", "ok", conn=conn)
    return {"opened": True, "ticket_ref": ref,
            "message": "Ticket opened. A technician visits within 48 hours."}


@router.post("/telco/retention-offer")
async def retention_offer(body: OfferReasonRequest, request: Request,
                          tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "get_retention_offer", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        offer = await conn.fetchrow("select * from cobranza.retention_offers where reason = $1", body.reason)
        svc = await conn.fetchrow("select monthly_price from cobranza.telco_services where customer_id = $1",
                                  customer["id"])
        await audit(tenant.id, body.conversation_id, "get_retention_offer", "ok", conn=conn)
    if offer is None or svc is None:
        return {"available": False, "message": "No retention offer for this case."}
    new_price = int(svc["monthly_price"]) * (100 - offer["discount_pct"]) // 100
    return {"available": True, "offer_id": offer["id"], "headline": offer["headline"],
            "discount_pct": offer["discount_pct"], "months": offer["months"],
            "new_price_text": money_text(new_price), "current_price_text": money_text(svc["monthly_price"]),
            "message": "Offer computed by policy. Present it exactly; do not improvise discounts."}


@router.post("/telco/accept-offer")
async def accept_offer(body: AcceptOfferRequest, request: Request,
                       tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "accept_retention_offer", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        offer = await conn.fetchrow("select id from cobranza.retention_offers where id = $1", body.offer_id)
        if offer is None:
            return {"applied": False, "message": "Unknown offer."}
        await conn.execute(
            "update cobranza.telco_services set applied_offer = $1, status = 'active' where customer_id = $2",
            offer["id"], customer["id"],
        )
        await audit(tenant.id, body.conversation_id, "accept_retention_offer", "ok", conn=conn)
    return {"applied": True, "message": "Offer applied to the next invoice."}


@router.post("/telco/cancel-service")
async def cancel_service(body: CancelServiceRequest, request: Request,
                         tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "confirm_cancellation", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        customer = await _customer(conn, body.session_token, "telco")
        ref = new_ref(tenant.id, "X")
        effective = date.today() + timedelta(days=CANCELLATION_NOTICE_DAYS)
        await conn.execute(
            "insert into cobranza.cancellations (ref, tenant_id, customer_id, reason, effective_date) values ($1, $2, $3, $4, $5)",
            ref, tenant.id, customer["id"], body.reason, effective,
        )
        await conn.execute("update cobranza.telco_services set status = 'cancelling' where customer_id = $1",
                           customer["id"])
        await audit(tenant.id, body.conversation_id, "confirm_cancellation", "ok", conn=conn)
    return {"cancelled": True, "cancellation_ref": ref, "effective_text": date_text(effective),
            "message": "Cancellation registered with the notice period."}


# ---------- inmobiliaria: leads (sin verificación de identidad) ----------

@router.post("/inmo/search")
async def search_properties(body: PropertySearchRequest, request: Request,
                            tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "search_properties", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        rows = await conn.fetch(
            """select * from cobranza.properties
               where ($1 = '' or zone ilike '%' || $1 || '%')
                 and ($2 = '' or kind = $2)
                 and ($3 = 0 or bedrooms >= $3)
                 and ($4 = 0 or price <= $4)
               order by price limit 3""",
            body.zone, body.kind, body.bedrooms, body.max_price,
        )
        await audit(tenant.id, body.conversation_id, "search_properties", "ok", conn=conn)
    return {"properties": [{"property_id": r["id"], "title": r["title"], "zone": r["zone"],
                            "bedrooms": r["bedrooms"], "kind": r["kind"],
                            "price_text": money_text(r["price"])} for r in rows],
            "message": "" if rows else "No properties match. Offer to widen the search."}


def _score(budget: int, timeline: str) -> str:
    if budget > 0 and timeline in ("inmediato", "1-3 meses"):
        return "alto"
    if budget > 0 or timeline == "3-6 meses":
        return "medio"
    return "bajo"


@router.post("/inmo/lead")
async def save_lead(body: SaveLeadRequest, request: Request, tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "save_lead", body.conversation_id)
    score = _score(body.budget, body.timeline)
    async with tenant_tx(tenant.id) as conn:
        lead_id = await conn.fetchval(
            """insert into cobranza.re_leads (id, tenant_id, conversation_id, name, zone, budget, bedrooms, timeline, score)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               on conflict (tenant_id, conversation_id) do update
                 set name = excluded.name, zone = excluded.zone, budget = excluded.budget,
                     bedrooms = excluded.bedrooms, timeline = excluded.timeline, score = excluded.score
               returning id""",
            new_ref(tenant.id, "L"), tenant.id, body.conversation_id, body.name, body.zone or None,
            body.budget or None, body.bedrooms or None, body.timeline, score,
        )
        await audit(tenant.id, body.conversation_id, "save_lead", score, conn=conn)
    return {"lead_id": lead_id, "score": score,
            "message": "Lead saved. If the score is alto, offer a visit with an advisor."}


@router.post("/inmo/advisor-slots")
async def advisor_slots(body: LeadSlotsRequest, request: Request,
                        tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "list_advisor_slots", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        await conn.execute("select cobranza.ensure_demo_slots()")
        rows = await conn.fetch(
            """select id, advisor, starts_at from cobranza.advisor_slots
               where not taken and starts_at > now() + interval '2 hours' order by starts_at limit 4""")
        await audit(tenant.id, body.conversation_id, "list_advisor_slots", "ok", conn=conn)
    return {"slots": [{"slot_id": r["id"], "advisor": r["advisor"], "when_text": _slot_text(r["starts_at"])}
                      for r in rows]}


@router.post("/inmo/book-advisor")
async def book_advisor(body: BookAdvisorRequest, request: Request,
                       tenant: Tenant = Depends(current_tenant)) -> dict:
    _demo_only(tenant)
    _track(request, "book_advisor", body.conversation_id)
    async with tenant_tx(tenant.id) as conn:
        lead_id = await conn.fetchval(
            "select id from cobranza.re_leads where conversation_id = $1", body.conversation_id)
        if lead_id is None:
            return {"booked": False, "message": "Save the lead first with save_lead."}
        slot = await conn.fetchrow(
            """update cobranza.advisor_slots set taken = true
               where id = $1 and not taken and starts_at > now() returning id, advisor, starts_at""",
            body.slot_id,
        )
        if slot is None:
            return {"booked": False, "message": "That slot is no longer available. Offer other options."}
        ref = new_ref(tenant.id, "V")
        await conn.execute(
            "insert into cobranza.advisor_bookings (ref, tenant_id, lead_id, slot_id) values ($1, $2, $3, $4)",
            ref, tenant.id, lead_id, slot["id"],
        )
        await audit(tenant.id, body.conversation_id, "book_advisor", "ok", conn=conn)
    return {"booked": True, "booking_ref": ref, "advisor": slot["advisor"],
            "when_text": _slot_text(slot["starts_at"]), "message": "Visit booked."}
