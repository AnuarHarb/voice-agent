import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    database_url: str
    console_database_url: str = ""
    console_allowed_origins: str = "*"
    public_base_url: str = "http://localhost:8000"
    post_call_webhook_secret: str = ""
    post_call_max_skew_secs: int = 30 * 60

    channel_mode: Literal["live", "log"] = "log"
    payment_link_ttl_hours: int = 48

    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v21.0"
    whatsapp_template_name: str = ""
    whatsapp_template_language: str = "es"

    telegram_bot_token: str = ""

    db_pool_min: int = 1
    db_pool_max: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


def tenant_secret(name: str, tenant_id: str) -> str:
    """Per-tenant credential override, e.g. TELEGRAM_BOT_TOKEN__NEXO, falling back to the shared one."""
    settings = get_settings()
    override = f"{name}__{tenant_id}".lower()
    extra = {k.lower(): v for k, v in (settings.model_extra or {}).items()}
    return (
        os.environ.get(override.upper())
        or extra.get(override)
        or getattr(settings, name.lower(), "")
    )
