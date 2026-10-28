import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_pool, connection, open_pool
from app.fintech_sim import console
from app.integration import compliance, payment_page, tools, verticals, webhooks
from app.integration.auth import ToolError, audit, tool_error_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Avanza Crédito · capa de integración",
    description="Webhook tools for the ElevenLabs collections agent.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_exception_handler(ToolError, tool_error_handler)
# Only the read-only console is meant to be called from a browser.
app.add_middleware(CORSMiddleware, allow_methods=["GET", "POST"], allow_headers=[],
                   allow_origins=[o.strip() for o in get_settings().console_allowed_origins.split(",") if o.strip()])


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Report which fields failed, never the values (they may contain personal data).
    fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors()})
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        await audit(tenant.id, None, request.url.path, "rejected:invalid_payload", {"fields": fields})
    return JSONResponse(status_code=422, content={"error": "invalid_payload", "fields": fields})


@app.get("/health", tags=["ops"])
async def health() -> dict:
    async with connection() as conn:
        await conn.fetchval("select 1")
    return {"status": "ok"}


app.include_router(tools.router)
app.include_router(verticals.router)
app.include_router(webhooks.router)
app.include_router(compliance.router)
app.include_router(payment_page.router)
app.include_router(console.router)
