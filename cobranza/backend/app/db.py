from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None
_console_pool: asyncpg.Pool | None = None


async def open_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        # statement_cache_size=0: Supabase's transaction pooler cannot keep
        # prepared statements across transactions.
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            statement_cache_size=0,
            server_settings={"search_path": "cobranza,public"},
        )
    return _pool


async def close_pool() -> None:
    global _pool, _console_pool
    for pool in (_pool, _console_pool):
        if pool is not None:
            await pool.close()
    _pool = _console_pool = None


@asynccontextmanager
async def connection() -> AsyncIterator[asyncpg.Connection]:
    pool = await open_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def tenant_tx(tenant_id: str) -> AsyncIterator[asyncpg.Connection]:
    """Transaction pinned to one tenant; row level security filters every query."""
    pool = await open_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id', $1, true)", tenant_id)
            yield conn


@asynccontextmanager
async def console_tx(tenant_id: str | None = None) -> AsyncIterator[asyncpg.Connection]:
    """Read-only transaction as cobranza_console, the back-office role that may read the vault."""
    global _console_pool
    if _console_pool is None:
        url = get_settings().console_database_url
        if not url:
            raise RuntimeError("CONSOLE_DATABASE_URL is not set")
        _console_pool = await asyncpg.create_pool(url, min_size=0, max_size=2, statement_cache_size=0,
                                                  server_settings={"search_path": "cobranza,public"})
    async with _console_pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            if tenant_id:
                await conn.execute("select set_config('app.tenant_id', $1, true)", tenant_id)
            yield conn
