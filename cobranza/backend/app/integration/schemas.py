"""Tool contracts. Every field the LLM fills is validated here; nothing is trusted as-is."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ConversationId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SessionToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=200)]
OptionalSessionToken = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: ConversationId


RawAnswer = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]


class VerifyIdentityRequest(ToolRequest):
    # Raw strings, parsed by the endpoint: an unreadable answer must lead to asking again, not to a tool error.
    id_last4: RawAnswer
    birth_date: RawAnswer

    def parsed(self) -> tuple[str | None, date | None]:
        last4 = self.id_last4 if re.fullmatch(r"\d{4}", self.id_last4) else None
        try:
            born = date.fromisoformat(self.birth_date)
        except ValueError:
            born = None
        if born and not date(1900, 1, 1) <= born <= date.today():
            born = None
        return last4, born


class SessionRequest(ToolRequest):
    session_token: SessionToken


class PaymentOptionsRequest(SessionRequest):
    promise_date: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ""


class CreatePlanRequest(SessionRequest):
    plan_id: Annotated[str, StringConstraints(pattern=r"^pln_[2-9A-HJKMNP-TV-Z]{12}$")]
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class PaymentLinkRequest(SessionRequest):
    plan_ref: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}-P-[2-9A-HJKMNP-TV-Z]{6}$")]


class DisputeRequest(SessionRequest):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class OptOutRequest(ToolRequest):
    session_token: OptionalSessionToken = ""
    phone_e164: Annotated[str, StringConstraints(pattern=r"^(\+[1-9]\d{7,14})?$")] = ""
    purpose: Annotated[str, StringConstraints(pattern=r"^(cobranza|comercial)$")] = "cobranza"


class SimulateOfferRequest(SessionRequest):
    offer_id: Annotated[str, StringConstraints(min_length=8, max_length=32)]
    term_months: Annotated[int, Field(ge=1, le=120)]


class ConfirmDisbursementRequest(SessionRequest):
    offer_id: Annotated[str, StringConstraints(min_length=8, max_length=32)]
    otp_code: Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


class CreditOfferResponse(BaseModel):
    available: bool
    offer_id: str = ""
    amount: int = 0
    amount_text: str = ""
    rate_ea_text: str = ""
    available_terms: list[int] = Field(default_factory=list)
    delinquent_product_code: str = ""
    message: str = ""


class SimulateOfferResponse(BaseModel):
    term_months: int
    installment_amount: int
    installment_amount_text: str
    rate_ea_text: str
    total_cost_text: str
    spoken_summary: str


class DisbursementOtpResponse(BaseModel):
    sent: bool
    channel: str
    message: str


class ConfirmDisbursementResponse(BaseModel):
    confirmed: bool
    disbursement_ref: str = ""
    amount_text: str = ""
    idempotent_replay: bool = False
    message: str = ""


class CallbackRequest(ToolRequest):
    session_token: OptionalSessionToken = ""
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
    preferred_window: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class VerifyIdentityResponse(BaseModel):
    verified: bool
    session_token: str
    customer_first_name: str = ""
    attempts_remaining: int
    locked: bool = False
    incomplete: bool = False
    message: str


class AccountSummaryResponse(BaseModel):
    account: str
    account_last4: str
    product: str
    overdue_amount: int
    overdue_amount_text: str
    total_balance: int
    total_balance_text: str
    days_past_due: int | None = None
    minimum_payment: int | None = None
    minimum_payment_text: str | None = None
    due_date: date | None = None
    due_date_text: str | None = None
    status: str


class PaymentOptionOut(BaseModel):
    plan_id: str
    kind: str
    installments: int
    installment_amount: int
    installment_amount_text: str
    last_installment_amount: int
    total_amount: int
    total_amount_text: str
    first_due_date: date
    first_due_date_text: str
    frequency: str
    hardship: bool


class PaymentOptionsResponse(BaseModel):
    options: list[PaymentOptionOut]
    hardship_option: PaymentOptionOut | None = None
    refinance_options: list[PaymentOptionOut] = Field(default_factory=list)
    promise_option: PaymentOptionOut | None = None
    escalate: bool = False
    discounts_available: bool = False
    note: str


class PaymentPlanResponse(BaseModel):
    plan_ref: str
    status: str
    installments: int
    installment_amount_text: str
    total_amount_text: str
    first_due_date: date
    first_due_date_text: str
    idempotent_replay: bool = False


class PaymentLinkResponse(BaseModel):
    sent: bool
    channel: str
    recipient: str
    already_sent: bool = False


class DisputeResponse(BaseModel):
    case_ref: str
    status: str
    next_step: str


class OptOutResponse(BaseModel):
    registered: bool
    linked_to_account: bool
    message: str


class CallbackResponse(BaseModel):
    callback_ref: str
    next_step: str


class ContactWindowResponse(BaseModel):
    allowed: bool
    channel: str
    evaluated_at: str
    reasons: list[str] = Field(default_factory=list)
    next_allowed_at: str | None = None
