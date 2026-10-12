"""Read-only back office of the simulated fintech: customers, debts, plans and calls.
It connects as cobranza_console, so row level security still scopes every query to one tenant."""

import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query

from app.db import console_tx

router = APIRouter(prefix="/console", tags=["fintech console"])

# Real ElevenLabs conversations start with conv_; pytest and smoke runs use other prefixes.
_REAL = r"conversation_id like 'conv\_%'"


def _plain(row) -> dict:
    out = {}
    for key, value in dict(row).items():
        if isinstance(value, Decimal):
            value = int(value)
        elif key == "detail" and isinstance(value, str):
            value = json.loads(value)
        out[key] = value
    return out


async def _rows(conn, sql: str, *args) -> list[dict]:
    return [_plain(r) for r in await conn.fetch(sql, *args)]


@router.get("/tenants")
async def tenants() -> list[dict]:
    async with console_tx() as conn:
        listed = await _rows(conn, "select id, name, channel from cobranza.tenants order by name")
    for tenant in listed:
        async with console_tx(tenant["id"]) as conn:
            tenant["agent_id"] = await conn.fetchval(
                "select agent_id from cobranza.tenant_agents where label = 'production' order by created_at limit 1")
    return listed


@router.get("/{tenant_id}/overview")
async def overview(tenant_id: str, include_tests: bool = Query(False)) -> dict:
    async with console_tx() as conn:
        tenant = await conn.fetchrow("select id, name, channel from cobranza.tenants where id = $1", tenant_id)
    if tenant is None:
        raise HTTPException(404, "unknown tenant")

    async with console_tx(tenant_id) as conn:
        policy = await conn.fetchrow("select * from cobranza.tenant_policies")
        customers = await _rows(conn, """
            select a.id as account_id, v.full_name, v.national_id, v.birth_date, v.phone_e164,
                   a.account_last4, a.product, a.overdue_amount, a.total_balance, a.days_past_due, a.status,
                   exists (select 1 from cobranza.contacts c where c.account_id = a.id and c.opt_out) as opted_out,
                   (select count(distinct c.conversation_id) from cobranza.contacts c
                     where c.account_id = a.id and c.""" + _REAL + """) as calls
            from cobranza.accounts a
            join cobranza.pii_vault v on v.person_token = a.person_token
            where $1 or a.id not like '%\\_pytest'
            order by a.days_past_due desc""", include_tests)
        plans = await _rows(conn, """
            select p.plan_ref, v.full_name, a.account_last4, p.installments, p.installment_amount,
                   p.total_amount, p.first_due_date, p.hardship, p.status, l.status as link_status,
                   l.channel as link_channel, l.sent_at as link_sent_at, p.conversation_id, p.created_at
            from cobranza.payment_plans p
            join cobranza.accounts a on a.id = p.account_id
            join cobranza.pii_vault v on v.person_token = a.person_token
            left join cobranza.payment_links l on l.plan_ref = p.plan_ref
            where $1 or p.""" + _REAL + """
            order by p.created_at desc""", include_tests)
        conversations = await _rows(conn, """
            with events as (
              select conversation_id, min(created_at) as first_event,
                     count(*) filter (where tool <> 'post_call_webhook') as tool_calls
              from cobranza.audit_log where conversation_id is not null group by conversation_id
            ), calls as (
              select coalesce(o.conversation_id, e.conversation_id) as conversation_id,
                     coalesce(o.received_at - make_interval(secs => coalesce(o.duration_secs, 0)), e.first_event)
                       as started_at,
                     coalesce(e.tool_calls, 0) as tool_calls, o.outcome, o.language, o.duration_secs,
                     o.call_successful, o.promise_amount, o.promise_date, o.late_reason, o.hardship
              from events e full join cobranza.call_outcomes o on o.conversation_id = e.conversation_id
            )
            select calls.*, who.full_name
            from calls
            left join lateral (
              select v.full_name
              from (select account_id from cobranza.contacts where conversation_id = calls.conversation_id
                    union all select account_id from cobranza.payment_plans where conversation_id = calls.conversation_id
                    union all select account_id from cobranza.disputes where conversation_id = calls.conversation_id
                    union all select account_id from cobranza.callbacks where conversation_id = calls.conversation_id) x
              join cobranza.accounts a on a.id = x.account_id
              join cobranza.pii_vault v on v.person_token = a.person_token
              limit 1
            ) who on true
            where $1 or calls.""" + _REAL + """
            order by started_at desc
            limit 50""", include_tests)
        cases = await _rows(conn, """
            select 'disputa' as kind, d.case_ref as ref, v.full_name, d.reason as summary, d.status,
                   d.conversation_id, d.created_at
            from cobranza.disputes d
            left join cobranza.accounts a on a.id = d.account_id
            left join cobranza.pii_vault v on v.person_token = a.person_token
            where $1 or d.""" + _REAL + """
            union all
            select 'llamada de asesor', c.callback_ref, v.full_name,
                   c.reason || ' (' || c.preferred_window || ')', c.status, c.conversation_id, c.created_at
            from cobranza.callbacks c
            left join cobranza.accounts a on a.id = c.account_id
            left join cobranza.pii_vault v on v.person_token = a.person_token
            where $1 or c.""" + _REAL + """
            union all
            select 'no contactar', 'NC-' || k.id, v.full_name, k.result, 'activo', k.conversation_id, k.contacted_at
            from cobranza.contacts k
            left join cobranza.accounts a on a.id = k.account_id
            left join cobranza.pii_vault v on v.person_token = a.person_token
            where k.opt_out and ($1 or k.""" + _REAL + """)
            order by created_at desc""", include_tests)

    return {
        "tenant": dict(tenant),
        "policy": _plain(policy) if policy else None,
        "customers": customers,
        "plans": plans,
        "conversations": conversations,
        "cases": cases,
        "generated_at": datetime.now(timezone.utc),
    }


@router.get("/{tenant_id}/conversations/{conversation_id}/events")
async def events(tenant_id: str, conversation_id: str) -> list[dict]:
    async with console_tx(tenant_id) as conn:
        return await _rows(conn, """
            select created_at, tool, result, detail from cobranza.audit_log
            where conversation_id = $1 order by id""", conversation_id)
