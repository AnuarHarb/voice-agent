"""Operator tasks that need the Supabase admin connection (DATABASE_ADMIN_URL).
The API server never uses that connection.

    uv run python scripts/admin.py issue-key avanza
    uv run python scripts/admin.py set-recipient acc_avz_0001 --phone +573001234567
    uv run python scripts/admin.py set-recipient acc_nxo_0001 --telegram-chat-id 123456789
    uv run python scripts/admin.py register-agent avanza agent_xxx
"""

import argparse
import asyncio
import os
import secrets
import sys

import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.integration.security import sha256_hex  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def connect() -> asyncpg.Connection:
    url = os.environ.get("DATABASE_ADMIN_URL")
    if not url:
        raise SystemExit("DATABASE_ADMIN_URL is required (Supabase postgres connection string)")
    return await asyncpg.connect(url, statement_cache_size=0)


async def issue_key(tenant: str) -> None:
    key = f"tk_{tenant}_{secrets.token_urlsafe(32)}"
    conn = await connect()
    try:
        updated = await conn.execute("update cobranza.tenants set key_hash = $1 where id = $2", sha256_hex(key), tenant)
    finally:
        await conn.close()
    if updated.endswith(" 0"):
        raise SystemExit(f"unknown tenant {tenant}")
    print(f"TENANT_KEY_{tenant.upper()}={key}")
    print("Only the hash is stored. Put this value in the agent push environment; the old key stops working now.")


async def set_recipient(account_id: str, phone: str | None, chat_id: str | None) -> None:
    conn = await connect()
    try:
        result = await conn.execute(
            """update cobranza.pii_vault v
               set phone_e164 = coalesce($2, v.phone_e164), telegram_chat_id = coalesce($3, v.telegram_chat_id)
               from cobranza.accounts a where a.person_token = v.person_token and a.id = $1""",
            account_id, phone, chat_id,
        )
    finally:
        await conn.close()
    print("updated" if result.endswith(" 1") else f"no account {account_id}")


async def register_agent(tenant: str, agent_id: str) -> None:
    conn = await connect()
    try:
        await conn.execute(
            """insert into cobranza.tenant_agents (agent_id, tenant_id, label) values ($1, $2, 'production')
               on conflict (agent_id) do update set tenant_id = excluded.tenant_id""",
            agent_id, tenant,
        )
    finally:
        await conn.close()
    print(f"{agent_id} -> {tenant}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("issue-key")
    p.add_argument("tenant")
    p = sub.add_parser("set-recipient")
    p.add_argument("account_id")
    p.add_argument("--phone", help="E.164, e.g. +573001234567")
    p.add_argument("--telegram-chat-id")
    p = sub.add_parser("register-agent")
    p.add_argument("tenant")
    p.add_argument("agent_id")
    args = parser.parse_args()
    if args.command == "issue-key":
        asyncio.run(issue_key(args.tenant))
    elif args.command == "set-recipient":
        asyncio.run(set_recipient(args.account_id, args.phone, args.telegram_chat_id))
    else:
        asyncio.run(register_agent(args.tenant, args.agent_id))


if __name__ == "__main__":
    main()
