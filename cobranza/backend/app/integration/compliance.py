"""Ley 2300 de 2023 ("Dejen de fregar") contact window, checked before any outbound contact.

- Monday to Friday 7 a.m. to 7 p.m., Saturday 8 a.m. to 3 p.m.; never Sundays or holidays.
- At most one outbound contact per day.
- No contact through a different channel in the same calendar week.
- Never after an opt-out; paused while a dispute is open.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query

from app.db import tenant_tx
from app.fintech_sim.holidays import is_holiday
from app.integration.auth import Tenant, ToolError, audit, current_tenant
from app.integration.schemas import ContactWindowResponse

router = APIRouter(prefix="/compliance", tags=["compliance"])

Channel = Literal["voice", "whatsapp", "telegram", "sms", "email"]


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
    hours: Hours,
    outbound_contacts: list[PastContact],
    opted_out: bool,
    in_dispute: bool,
) -> tuple[bool, list[str], datetime | None]:
    """`now` and contact times must be in the tenant's local timezone."""
    if opted_out:
        return False, ["customer_opted_out"], None
    if in_dispute:
        return False, ["dispute_open"], None

    def violations(at: datetime) -> list[str]:
        reasons = []
        window = _window(at.date(), hours)
        if window is None:
            reasons.append("sunday_or_holiday")
        elif not window[0] <= at.time() < window[1]:
            reasons.append("outside_legal_hours")
        if any(c.at.date() == at.date() for c in outbound_contacts):
            reasons.append("already_contacted_today")
        if any(_week_start(c.at.date()) == _week_start(at.date()) and c.channel != channel
               for c in outbound_contacts):
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
    account_id: str = Query(min_length=1, max_length=64),
    channel: Channel = Query(default="voice"),
    at: datetime | None = Query(default=None, description="ISO datetime to evaluate; defaults to now"),
    tenant: Tenant = Depends(current_tenant),
) -> ContactWindowResponse:
    async with tenant_tx(tenant.id) as conn:
        account = await conn.fetchrow("select status from cobranza.accounts where id = $1", account_id)
        if account is None:
            raise ToolError(404, "account_not_found", "Unknown account for this tenant.")
        policy = await conn.fetchrow("select * from cobranza.tenant_policies")
        tz = ZoneInfo(policy["timezone"])
        if at is not None and at.tzinfo is None:
            at = at.replace(tzinfo=tz)
        now = (at or datetime.now(tz)).astimezone(tz)
        rows = await conn.fetch(
            """select contacted_at, channel, opt_out, direction from cobranza.contacts
               where account_id = $1 and (opt_out or contacted_at > $2::timestamptz - interval '8 days')""",
            account_id, now,
        )
        hours = Hours(policy["weekday_start_hour"], policy["weekday_end_hour"],
                      policy["saturday_start_hour"], policy["saturday_end_hour"])
        outbound = [PastContact(r["contacted_at"].astimezone(tz), r["channel"])
                    for r in rows if r["direction"] == "outbound"]
        allowed, reasons, next_at = evaluate_contact_window(
            now, channel, hours, outbound,
            opted_out=any(r["opt_out"] for r in rows),
            in_dispute=account["status"] == "in_dispute",
        )
        await audit(tenant.id, None, "contact_window", "allowed" if allowed else "blocked",
                    {"account_id": account_id, "channel": channel, "reasons": reasons}, conn=conn)
    return ContactWindowResponse(
        allowed=allowed, channel=channel, evaluated_at=now.isoformat(), reasons=reasons,
        next_allowed_at=next_at.isoformat() if next_at else None,
    )
