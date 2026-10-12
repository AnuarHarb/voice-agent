import json
import logging
from dataclasses import dataclass

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from app.db import connection, tenant_tx
from app.integration.security import sha256_hex

log = logging.getLogger("cobranza.auth")


@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    channel: str


class ToolError(Exception):
    """A rejected tool call. It is written to the audit log and returned as a non-2xx response,
    which the agent treats as a tool failure and handles with on_failure."""

    def __init__(self, status: int, code: str, message: str, audited: bool = False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.audited = audited


async def current_tenant(
    request: Request,
    x_tenant_key: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> Tenant:
    if not x_tenant_key:
        raise ToolError(401, "missing_tenant_key", "X-Tenant-Key header is required.")
    async with connection() as conn:
        row = await conn.fetchrow("select * from cobranza.resolve_tenant($1)", sha256_hex(x_tenant_key))
    if row is None:
        log.warning("rejected unknown tenant key on %s", request.url.path)
        raise ToolError(401, "invalid_tenant_key", "Unknown tenant key.")
    tenant = Tenant(id=row["id"], name=row["name"], channel=row["channel"])
    request.state.tenant = tenant
    # Defense in depth: the agent also sends its configured tenant_id; it must match the key.
    if x_tenant_id and x_tenant_id != tenant.id:
        raise ToolError(403, "tenant_mismatch", "Tenant id does not match the tenant key.")
    return tenant


async def audit(tenant_id: str, conversation_id: str | None, tool: str, result: str, detail: dict | None = None,
                conn=None) -> None:
    sql = ("insert into cobranza.audit_log (tenant_id, conversation_id, tool, result, detail) "
           "values ($1, $2, $3, $4, $5::jsonb)")
    args = (tenant_id, conversation_id, tool, result, json.dumps(detail or {}))
    if conn is not None:
        await conn.execute(sql, *args)
        return
    async with tenant_tx(tenant_id) as own:
        await own.execute(sql, *args)


async def tool_error_handler(request: Request, exc: ToolError) -> JSONResponse:
    tenant: Tenant | None = getattr(request.state, "tenant", None)
    if tenant is not None and not exc.audited:
        await audit(
            tenant.id,
            getattr(request.state, "conversation_id", None),
            getattr(request.state, "tool", request.url.path),
            f"rejected:{exc.code}",
        )
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "message": exc.message})
