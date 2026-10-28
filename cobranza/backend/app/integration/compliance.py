"""Ley 2300 contact window by purpose (cobranza vs comercial)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query

from app.db import tenant_tx
from app.fintech_sim.holidays import is_holiday
from app.fintech_sim.policy import parse_product_policy
from app.integration.auth import Tenant, ToolError, audit, current_tenant
from app.integration.schemas import ContactWindowResponse

router = APIRouter(prefix="/compliance", tags=["compliance"])

Channel = Literal["voice", "whatsapp", "telegram", "sms", "email"]
Purpose = Literal["cobranza", "comercial"]


@dataclass(frozen=True)
class Hours:
    weekday_start: int = 7
    weekday_end: int = 19
    saturday_start: int = 8
    saturday_end: int = 15


@dataclass(frozen=True)
class PastContact:
    at: datetime
    channel: str
    purpose: str


def _window(day: date, hours: Hours) -> tuple[time, time] | None:
    if day.weekday() == 6 or is_holiday(day):
        return None
    if day.weekday() == 5:
        return time(hours.saturday_start), time(hours.saturday_end)
    return time(hours.weekday_start), time(hours.weekday_end)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def evaluate_contact_window(
    now: datetime,
    channel: str,
    purpose: str,
    hours: Hours,
    outbound_contacts: list[PastContact],
    opted_out: bool,
    in_dispute: bool,
    has_consent: bool,
) -> tuple[bool, list[str], datetime | None]:
    if not has_consent:
        return False, ["no_consent"], None
    if opted_out:
        return False, ["customer_opted_out"], None
    if in_dispute and purpose == "cobranza":
        return False, ["dispute_open"], None

    def violations(at: datetime) -> list[str]:
        reasons = []
        window = _window(at.date(), hours)
        if window is None:
            reasons.append("sunday_or_holiday")
        elif not window[0] <= at.time() < window[1]:
            reasons.append("outside_legal_hours")
        same_purpose = [c for c in outbound_contacts if c.purpose == purpose]
        if any(c.at.date() == at.date() for c in same_purpose):
            reasons.append("already_contacted_today")
        if any(_week_start(c.at.date()) == _week_start(at.date()) and c.channel != channel
               for c in same_purpose):
            reasons.append("other_channel_used_this_week")
        return reasons

    reasons = violations(now)
    if not reasons:
        return True, [], None

    for offset in range(0, 15):
        day = now.date() + timedelta(days=offset)
        window = _window(day, hours)
        if window is None:
            continue
        start = datetime.combine(day, window[0], tzinfo=now.tzinfo)
        candidate = max(start, now) if offset == 0 else start
        if candidate.time() < window[1] and not violations(candidate):
            return False, reasons, candidate
    return False, reasons, None


@router.get("/contact-window", response_model=ContactWindowResponse)
async def contact_window(
    person_id: str = Query(min_length=1, max_length=64),
    purpose: Purpose = Query(default="cobranza"),
    channel: Channel = Query(default="voice"),
    at: datetime | None = Query(default=None, description="ISO datetime to evaluate; defaults to now"),
    tenant: Tenant = Depends(current_tenant),
) -> ContactWindowResponse:
    async with tenant_tx(tenant.id) as conn:
        exists = await conn.fetchval(
            "select 1 from cobranza.accounts where person_token = $1 limit 1", person_id
        )
        if exists is None:
            raise ToolError(404, "person_not_found", "Unknown person for this tenant.")
        policy_row = await conn.fetchrow("select policy from cobranza.product_policies limit 1")
        if policy_row is None:
            raise ToolError(500, "policy_missing", "Tenant has no credit policy configured.")
        parsed = parse_product_policy(policy_row["policy"])
        tz = ZoneInfo(parsed.timezone)
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=tz)
        now = (at or datetime.now(tz)).astimezone(tz)
        has_consent = await conn.fetchval(
            """select exists(
                 select 1 from cobranza.contact_consents
                 where person_token = $1 and purpose = $2 and channel = $3 and revoked_at is null)""",
            person_id, purpose, channel,
        )
        rows = await conn.fetch(
            """select c.contacted_at, c.channel, c.opt_out, c.direction, c.purpose
               from cobranza.contacts c
               join cobranza.accounts a on a.id = c.account_id
               where a.person_token = $1
                 and (c.opt_out or c.contacted_at > $2::timestamptz - interval '8 days')""",
            person_id, now,
        )
        hours = Hours(parsed.weekday_start_hour, parsed.weekday_end_hour,
                      parsed.saturday_start_hour, parsed.saturday_end_hour)
        outbound = [
            PastContact(r["contacted_at"].astimezone(tz), r["channel"], r["purpose"])
            for r in rows if r["direction"] == "outbound"
        ]
        opted_out = any(r["opt_out"] and r["purpose"] == purpose for r in rows)
        in_dispute = await conn.fetchval(
            """select exists(select 1 from cobranza.accounts
               where person_token = $1 and status = 'in_dispute')""",
            person_id,
        )
        allowed, reasons, next_at = evaluate_contact_window(
            now, channel, purpose, hours, outbound, opted_out, in_dispute, has_consent,
        )
        await audit(tenant.id, None, "contact_window", "allowed" if allowed else "blocked",
                    {"person_id": person_id, "purpose": purpose, "channel": channel, "reasons": reasons},
                    conn=conn)
    return ContactWindowResponse(
        allowed=allowed, channel=channel, evaluated_at=now.isoformat(), reasons=reasons,
        next_allowed_at=next_at.isoformat() if next_at else None,
    )
