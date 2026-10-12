from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Recipient:
    phone_e164: str | None
    telegram_chat_id: str | None


@dataclass(frozen=True)
class PaymentLinkMessage:
    first_name: str
    tenant_name: str
    plan_ref: str
    amount_text: str
    due_text: str
    link: str

    def as_text(self) -> str:
        greeting = f"Hola {self.first_name}" if self.first_name else "Hola"
        return (
            f"{greeting}, este es tu link de pago de {self.tenant_name} para el plan {self.plan_ref}: "
            f"{self.amount_text}, primera fecha {self.due_text}. {self.link}"
        )


class ChannelError(Exception):
    pass


class MessageChannel(Protocol):
    name: str

    def recipient_label(self, recipient: Recipient) -> str: ...

    async def send_payment_link(self, recipient: Recipient, message: PaymentLinkMessage) -> str:
        """Sends the message and returns the provider's message id."""
        ...
