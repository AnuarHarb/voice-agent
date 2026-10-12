import httpx

from app.config import get_settings, tenant_secret
from app.integration.channels.base import ChannelError, PaymentLinkMessage, Recipient
from app.integration.formatting import mask_tail


class WhatsAppChannel:
    """WhatsApp Cloud API. Business-initiated messages need an approved utility template;
    without WHATSAPP_TEMPLATE_NAME it sends free text, which Meta only delivers inside the
    24-hour window after the customer last wrote to the business number."""

    name = "whatsapp"

    def __init__(self, tenant_id: str):
        settings = get_settings()
        self.token = tenant_secret("WHATSAPP_ACCESS_TOKEN", tenant_id)
        self.phone_number_id = tenant_secret("WHATSAPP_PHONE_NUMBER_ID", tenant_id)
        self.template = tenant_secret("WHATSAPP_TEMPLATE_NAME", tenant_id)
        self.language = settings.whatsapp_template_language
        self.url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{self.phone_number_id}/messages"

    def recipient_label(self, recipient: Recipient) -> str:
        return f"WhatsApp {mask_tail(recipient.phone_e164)}"

    def _payload(self, to: str, message: PaymentLinkMessage) -> dict:
        if self.template:
            return {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": self.template,
                    "language": {"code": self.language},
                    "components": [{
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": message.first_name or "cliente"},
                            {"type": "text", "text": message.amount_text},
                            {"type": "text", "text": message.due_text},
                            {"type": "text", "text": message.link},
                        ],
                    }],
                },
            }
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": True, "body": message.as_text()},
        }

    async def send_payment_link(self, recipient: Recipient, message: PaymentLinkMessage) -> str:
        if not (self.token and self.phone_number_id):
            raise ChannelError("WhatsApp credentials are not configured")
        if not recipient.phone_e164:
            raise ChannelError("customer has no WhatsApp number on file")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=self._payload(recipient.phone_e164.lstrip("+"), message),
            )
        if response.status_code >= 300:
            raise ChannelError(f"WhatsApp API returned {response.status_code}: {response.text[:300]}")
        return response.json()["messages"][0]["id"]
