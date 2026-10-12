import hashlib
import hmac
import secrets
import time

_REF_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_session_token() -> str:
    return "st_" + secrets.token_urlsafe(32)


def new_link_token() -> str:
    return secrets.token_urlsafe(24)


def new_plan_id() -> str:
    return "pln_" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(12))


def new_ref(tenant_id: str, kind: str) -> str:
    """Short, speakable reference such as AVA-P-7K3Q9X."""
    suffix = "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
    return f"{tenant_id[:3].upper()}-{kind}-{suffix}"


def verify_elevenlabs_signature(
    raw_body: bytes, header: str | None, secret: str, max_skew_secs: int, now: float | None = None
) -> bool:
    """Validates the `ElevenLabs-Signature: t=<unix>,v0=<hmac_sha256(secret, "t.body")>` header."""
    if not header or not secret:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    timestamp, signature = parts.get("t"), parts.get("v0")
    if not timestamp or not signature or not timestamp.isdigit():
        return False
    now = time.time() if now is None else now
    if abs(now - int(timestamp)) > max_skew_secs:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
