"""Post-call webhook: stores the call outcome (data collection + evaluation), never the transcript."""

import json
import logging
import re
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import connection, tenant_tx
from app.integration.auth import audit
from app.integration.security import verify_elevenlabs_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("cobranza.webhooks")

_OUTCOMES = {"promesa", "disputa", "escalado", "opt_out", "sin_acuerdo"}


def _value(results: dict, key: str):
    item = results.get(key) or {}
    value = item.get("value") if isinstance(item, dict) else None
    return None if value in ("", "null", "None") else value


def _as_bool(value) -> bool | None:
    if isinstance(value, bool) or value is None:
        return value
    return str(value).strip().lower() in ("true", "yes", "si", "sí", "1")


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _as_amount(value) -> int | None:
    """Accepts 1200000, "1200000.0" or a Colombian-formatted "$1.200.000"."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    try:
        return int(round(float(value)))
    except ValueError:
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None


def _score(value) -> float | None:
    try:
        return max(-1.0, min(1.0, round(float(value), 2)))
    except (TypeError, ValueError):
        return None


@router.post("/post-call")
async def post_call(request: Request) -> JSONResponse:
    settings = get_settings()
    raw = await request.body()
    if not verify_elevenlabs_signature(raw, request.headers.get("elevenlabs-signature"),
                                       settings.post_call_webhook_secret, settings.post_call_max_skew_secs):
        return JSONResponse(status_code=401, content={"error": "invalid_signature"})

    payload = json.loads(raw)
    if payload.get("type") != "post_call_transcription":
        return JSONResponse(content={"status": "ignored", "type": payload.get("type")})

    data = payload.get("data") or {}
    agent_id, conversation_id = data.get("agent_id"), data.get("conversation_id")
    async with connection() as conn:
        tenant = await conn.fetchrow("select * from cobranza.tenant_by_agent($1)", agent_id)
    if tenant is None or not conversation_id:
        log.warning("post-call webhook for unknown agent %s", agent_id)
        return JSONResponse(content={"status": "ignored", "reason": "unknown_agent"})

    analysis = data.get("analysis") or {}
    results = analysis.get("data_collection_results") or {}
    evaluation = {k: (v or {}).get("result") for k, v in (analysis.get("evaluation_criteria_results") or {}).items()}
    outcome = _value(results, "outcome")
    outcome = outcome if outcome in _OUTCOMES else ("sin_acuerdo" if outcome else None)
    language = _value(results, "language")
    sentiment = analysis.get("sentiment_analysis") or {}
    label = sentiment.get("overall_label")

    async with tenant_tx(tenant["id"]) as conn:
        await conn.execute(
            """insert into cobranza.call_outcomes
               (conversation_id, tenant_id, agent_id, outcome, promise_amount, promise_date, late_reason,
                hardship, language, call_successful, evaluation, duration_secs,
                sentiment_label, sentiment_score, frustration_score, min_sentiment_score)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13, $14, $15, $16)
               on conflict (conversation_id) do update set
                 outcome = excluded.outcome, promise_amount = excluded.promise_amount,
                 promise_date = excluded.promise_date, late_reason = excluded.late_reason,
                 hardship = excluded.hardship, language = excluded.language,
                 call_successful = excluded.call_successful, evaluation = excluded.evaluation,
                 duration_secs = excluded.duration_secs, sentiment_label = excluded.sentiment_label,
                 sentiment_score = excluded.sentiment_score, frustration_score = excluded.frustration_score,
                 min_sentiment_score = excluded.min_sentiment_score, received_at = now()""",
            conversation_id, tenant["id"], agent_id, outcome,
            _as_amount(_value(results, "promise_amount")), _as_date(_value(results, "promise_date")),
            (str(_value(results, "late_reason") or "")[:200] or None), _as_bool(_value(results, "hardship")),
            (str(language)[:5] if language else None), analysis.get("call_successful"),
            json.dumps(evaluation), (data.get("metadata") or {}).get("call_duration_secs"),
            label if label in ("positive", "neutral", "negative") else None,
            _score(sentiment.get("overall_sentiment_score")), _score(sentiment.get("overall_frustration_score")),
            _score(sentiment.get("min_user_sentiment_score")),
        )
        account_id = await conn.fetchval(
            "select account_id from cobranza.sessions where conversation_id = $1 order by created_at desc limit 1",
            conversation_id,
        )
        await conn.execute(
            """insert into cobranza.contacts (tenant_id, account_id, channel, direction, result, opt_out, conversation_id)
               values ($1, $2, 'voice', 'inbound', $3, $4, $5)""",
            tenant["id"], account_id, outcome or "unknown", outcome == "opt_out", conversation_id,
        )
        await audit(tenant["id"], conversation_id, "post_call_webhook", "stored",
                    {"outcome": outcome, "evaluation": evaluation}, conn=conn)
    return JSONResponse(content={"status": "stored"})
