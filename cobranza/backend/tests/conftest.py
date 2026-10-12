import os
import uuid

import httpx
import pytest
from dotenv import dotenv_values

from app.db import close_pool, open_pool, tenant_tx
from app.main import app

_ENV = {**dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env")), **os.environ}

LAURA = {"id_last4": "4417", "birth_date": "1990-05-14"}
FIXTURE = {"id_last4": "0001", "birth_date": "2000-01-01"}
FIXTURE_ACCOUNT = "acc_avz_pytest"


def env(name: str) -> str:
    value = _ENV.get(name)
    if not value:
        pytest.skip(f"{name} is not set")
    return value


@pytest.fixture(scope="session")
def avanza_key() -> str:
    return env("TENANT_KEY_AVANZA")


@pytest.fixture(scope="session")
def nexo_key() -> str:
    return env("TENANT_KEY_NEXO")


@pytest.fixture(scope="session")
async def client():
    env("DATABASE_URL")
    await open_pool()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_pool()


@pytest.fixture
def conversation_id() -> str:
    return f"pytest-{uuid.uuid4().hex[:12]}"


async def verify(client: httpx.AsyncClient, key: str, conversation_id: str, identity: dict) -> dict:
    response = await client.post(
        "/tools/verify-identity",
        headers={"X-Tenant-Key": key},
        json={"conversation_id": conversation_id, **identity},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def audit_rows(tenant_id: str, conversation_id: str) -> list[dict]:
    async with tenant_tx(tenant_id) as conn:
        rows = await conn.fetch(
            "select tool, result, detail from cobranza.audit_log where conversation_id = $1 order by id",
            conversation_id,
        )
    return [dict(r) for r in rows]


@pytest.fixture
async def reset_fixture_account():
    yield
    async with tenant_tx("avanza") as conn:
        await conn.execute("update cobranza.accounts set status = 'active' where id = $1", FIXTURE_ACCOUNT)
