import httpx

from app.config import tenant_secret
from app.integration.channels.base import ChannelError, PaymentLinkMessage, Recipient


class TelegramChannel:
    """Telegram Bot API. The customer must have messaged the bot once so we know their chat_id."""

    name = "telegram"

    def __init__(self, tenant_id: str):
        self.token = tenant_secret("TELEGRAM_BOT_TOKEN", tenant_id).strip().strip("'\"")

    def recipient_label(self, recipient: Recipient) -> str:
        return "Telegram"

    async def send_payment_link(self, recipient: Recipient, message: PaymentLinkMessage) -> str:
        if not self.token:
            raise ChannelError("Telegram bot token is not configured")
        if not recipient.telegram_chat_id:
            raise ChannelError("customer has no Telegram chat_id on file")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": recipient.telegram_chat_id, "text": message.as_text()},
            )
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.status_code >= 300 or not body.get("ok"):
            raise ChannelError(f"Telegram API returned {response.status_code}: {response.text[:300]}")
        return str(body["result"]["message_id"])
