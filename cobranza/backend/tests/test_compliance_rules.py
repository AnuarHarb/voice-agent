import hashlib
import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

from app.integration.compliance import Hours, PastContact, evaluate_contact_window
from app.integration.security import verify_elevenlabs_signature

BOG = ZoneInfo("America/Bogota")
HOURS = Hours()


def at(*args) -> datetime:
    return datetime(*args, tzinfo=BOG)


def check(now, channel="voice", contacts=(), opted_out=False, in_dispute=False, has_consent=True, purpose="cobranza"):
    return evaluate_contact_window(now, channel, purpose, HOURS, list(contacts), opted_out, in_dispute, has_consent)


def test_weekday_inside_legal_hours_is_allowed():
    assert check(at(2026, 10, 13, 10, 0)) == (True, [], None)


def test_before_seven_waits_until_seven():
    allowed, reasons, next_at = check(at(2026, 10, 13, 6, 30))
    assert not allowed and reasons == ["outside_legal_hours"]
    assert next_at == at(2026, 10, 13, 7, 0)


def test_saturday_closes_at_three():
    allowed, reasons, next_at = check(at(2026, 10, 17, 15, 0))
    assert not allowed and reasons == ["outside_legal_hours"]
    assert next_at == at(2026, 10, 19, 7, 0)  # Sunday skipped


def test_sunday_and_holiday_are_blocked():
    allowed, reasons, next_at = check(at(2026, 10, 11, 10, 0))  # Sunday
    assert not allowed and reasons == ["sunday_or_holiday"]
    assert next_at == at(2026, 10, 13, 7, 0)  # Monday Oct 12 is Día de la Raza

    allowed, reasons, _ = check(at(2026, 10, 12, 10, 0))
    assert not allowed and reasons == ["sunday_or_holiday"]


def test_only_one_contact_per_day():
    contacts = [PastContact(at(2026, 10, 13, 8, 0), "voice", "cobranza")]
    allowed, reasons, next_at = check(at(2026, 10, 13, 16, 0), contacts=contacts)
    assert not allowed and reasons == ["already_contacted_today"]
    assert next_at == at(2026, 10, 14, 7, 0)


def test_no_second_channel_in_the_same_week():
    contacts = [PastContact(at(2026, 10, 13, 8, 0), "whatsapp", "cobranza")]
    allowed, reasons, next_at = check(at(2026, 10, 15, 10, 0), channel="voice", contacts=contacts)
    assert not allowed and reasons == ["other_channel_used_this_week"]
    assert next_at == at(2026, 10, 19, 7, 0)

    allowed, _, _ = check(at(2026, 10, 15, 10, 0), channel="whatsapp", contacts=contacts)
    assert allowed


def test_opt_out_and_dispute_block_without_next_slot():
    assert check(at(2026, 10, 13, 10, 0), opted_out=True) == (False, ["customer_opted_out"], None)
    assert check(at(2026, 10, 13, 10, 0), in_dispute=True) == (False, ["dispute_open"], None)


def _sign(secret: str, body: bytes, ts: int) -> str:
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v0={digest}"


def test_post_call_signature():
    body, secret, ts = b'{"type":"post_call_transcription"}', "wsec_test", 1_800_000_000
    header = _sign(secret, body, ts)
    assert verify_elevenlabs_signature(body, header, secret, 1800, now=ts + 10)
    assert not verify_elevenlabs_signature(body + b" ", header, secret, 1800, now=ts + 10)
    assert not verify_elevenlabs_signature(body, header, "other", 1800, now=ts + 10)
    assert not verify_elevenlabs_signature(body, header, secret, 1800, now=ts + 3600)
    assert not verify_elevenlabs_signature(body, None, secret, 1800, now=ts)
