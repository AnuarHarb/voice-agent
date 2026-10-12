import logging
import secrets

from app.config import get_settings
from app.integration.channels.base import (
    ChannelError,
    MessageChannel,
    PaymentLinkMessage,
    Recipient,
)
from app.integration.channels.telegram import TelegramChannel
from app.integration.channels.whatsapp import WhatsAppChannel

log = logging.getLogger("cobranza.channels")

__all__ = ["ChannelError", "MessageChannel", "PaymentLinkMessage", "Recipient", "get_channel"]


class LogChannel:
    """CHANNEL_MODE=log: records the message instead of sending it (local runs and tests)."""

    def __init__(self, inner: MessageChannel):
        self.inner = inner
        self.name = inner.name

    def recipient_label(self, recipient: Recipient) -> str:
        return self.inner.recipient_label(recipient)

    async def send_payment_link(self, recipient: Recipient, message: PaymentLinkMessage) -> str:
        message_id = f"log-{secrets.token_hex(6)}"
        log.info("[%s dry-run] %s -> %s", self.name, message_id, message.link)
        return message_id


def get_channel(tenant_id: str, channel: str) -> MessageChannel:
    implementation = {"whatsapp": WhatsAppChannel, "telegram": TelegramChannel}[channel](tenant_id)
    if get_settings().channel_mode == "log":
        return LogChannel(implementation)
    return implementation
