"""Credit policy per product: the only source of payment amounts and dates."""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from app.fintech_sim.holidays import next_business_day

OptionKind = Literal["full", "installments", "hardship", "minimum", "refinance", "promise"]


@dataclass(frozen=True)
class Policy:
    max_installments: int
    min_installment_cop: int
    first_payment_max_days: int
    hardship_enabled: bool
    hardship_installments: int
    hardship_grace_days: int
    escalate_when_days_past_due_gt: int | None = None


@dataclass(frozen=True)
class ProductPolicyRow:
    timezone: str
    weekday_start_hour: int
    weekday_end_hour: int
    saturday_start_hour: int
    saturday_end_hour: int
    session_ttl_minutes: int
    max_verification_attempts: int
    options: dict[str, Any]


@dataclass(frozen=True)
class PlanOption:
    kind: OptionKind
    installments: int
    installment_amount: int
    last_installment_amount: int
    total_amount: int
    first_due_date: date
    hardship: bool


@dataclass(frozen=True)
class PaymentOptionsResult:
    options: list[PlanOption]
    hardship_option: PlanOption | None
    refinance_options: list[PlanOption]
    promise_option: PlanOption | None = None
    escalate: bool = False


def parse_product_policy(raw: dict) -> ProductPolicyRow:
    opts = raw.get("options") or {}
    return ProductPolicyRow(
        timezone=raw.get("timezone", "America/Bogota"),
        weekday_start_hour=int(raw.get("weekday_start_hour", 7)),
        weekday_end_hour=int(raw.get("weekday_end_hour", 19)),
        saturday_start_hour=int(raw.get("saturday_start_hour", 8)),
        saturday_end_hour=int(raw.get("saturday_end_hour", 15)),
        session_ttl_minutes=int(raw.get("session_ttl_minutes", 30)),
        max_verification_attempts=int(raw.get("max_verification_attempts", 3)),
        options=opts,
    )


def overdue_policy_from_options(opts: dict[str, Any]) -> Policy:
    return Policy(
        max_installments=int(opts.get("max_installments", 3)),
        min_installment_cop=int(opts.get("min_installment_cop", 150_000)),
        first_payment_max_days=int(opts.get("first_payment_max_days", 5)),
        hardship_enabled=bool(opts.get("hardship_enabled", False)),
        hardship_installments=int(opts.get("hardship_installments", 6)),
        hardship_grace_days=int(opts.get("hardship_grace_days", 30)),
        escalate_when_days_past_due_gt=opts.get("escalate_when_days_past_due_gt"),
    )


def _split(total: int, parts: int) -> tuple[int, int]:
    installment = math.ceil(total / parts / 100) * 100
    last = total - installment * (parts - 1)
    return installment, last


def payment_options_overdue(overdue_amount: int, policy: Policy, today: date) -> list[PlanOption]:
    if overdue_amount <= 0:
        return []

    options = [
        PlanOption(
            kind="full",
            installments=1,
            installment_amount=overdue_amount,
            last_installment_amount=overdue_amount,
            total_amount=overdue_amount,
            first_due_date=next_business_day(today + timedelta(days=policy.first_payment_max_days)),
            hardship=False,
        )
    ]

    parts = min(policy.max_installments, overdue_amount // policy.min_installment_cop)
    if parts >= 2:
        installment, last = _split(overdue_amount, parts)
        options.append(
            PlanOption(
                kind="installments",
                installments=parts,
                installment_amount=installment,
                last_installment_amount=last,
                total_amount=overdue_amount,
                first_due_date=next_business_day(today + timedelta(days=7)),
                hardship=False,
            )
        )

    if policy.hardship_enabled and policy.hardship_installments >= 2:
        installment, last = _split(overdue_amount, policy.hardship_installments)
        options.append(
            PlanOption(
                kind="hardship",
                installments=policy.hardship_installments,
                installment_amount=installment,
                last_installment_amount=last,
                total_amount=overdue_amount,
                first_due_date=next_business_day(today + timedelta(days=policy.hardship_grace_days)),
                hardship=True,
            )
        )

    return options


def payment_options_card_preventive(
    total_balance: int, minimum_payment: int, opts: dict[str, Any], today: date
) -> tuple[list[PlanOption], list[PlanOption]]:
    main: list[PlanOption] = []
    refinance: list[PlanOption] = []
    if minimum_payment <= 0 and total_balance <= 0:
        return main, refinance

    if minimum_payment > 0:
        main.append(
            PlanOption(
                kind="minimum",
                installments=1,
                installment_amount=minimum_payment,
                last_installment_amount=minimum_payment,
                total_amount=minimum_payment,
                first_due_date=next_business_day(today),
                hardship=False,
            )
        )
    if total_balance > 0:
        main.append(
            PlanOption(
                kind="full",
                installments=1,
                installment_amount=total_balance,
                last_installment_amount=total_balance,
                total_amount=total_balance,
                first_due_date=next_business_day(today),
                hardship=False,
            )
        )

    min_ref = int(opts.get("refinance_min_balance_cop", 500_000))
    if total_balance >= min_ref:
        for term in opts.get("refinance_terms", [6, 12, 24]):
            term = int(term)
            installment, last = _split(total_balance, term)
            refinance.append(
                PlanOption(
                    kind="refinance",
                    installments=term,
                    installment_amount=installment,
                    last_installment_amount=last,
                    total_amount=total_balance,
                    first_due_date=next_business_day(today + timedelta(days=30)),
                    hardship=False,
                )
            )
    return main, refinance


def payment_options_promise(overdue_amount: int, promise_date: date | None, opts: dict[str, Any], today: date) -> list[PlanOption]:
    if overdue_amount <= 0:
        return []
    options = [
        PlanOption(
            kind="full",
            installments=1,
            installment_amount=overdue_amount,
            last_installment_amount=overdue_amount,
            total_amount=overdue_amount,
            first_due_date=next_business_day(today),
            hardship=False,
        )
    ]
    max_days = int(opts.get("promise_max_days", 7))
    if promise_date is not None:
        if promise_date > today + timedelta(days=max_days):
            raise ValueError("promise_outside_window")
        if promise_date < today:
            raise ValueError("promise_in_past")
        options.append(
            PlanOption(
                kind="promise",
                installments=1,
                installment_amount=overdue_amount,
                last_installment_amount=overdue_amount,
                total_amount=overdue_amount,
                first_due_date=next_business_day(promise_date),
                hardship=False,
            )
        )
    return options


def payment_options_for_account(
    *,
    mode: str,
    overdue_amount: int,
    total_balance: int,
    minimum_payment: int,
    days_past_due: int,
    policy_opts: dict[str, Any],
    today: date,
    promise_date: date | None = None,
) -> PaymentOptionsResult:
    if mode == "overdue":
        pol = overdue_policy_from_options(policy_opts)
        if pol.escalate_when_days_past_due_gt is not None and days_past_due > pol.escalate_when_days_past_due_gt:
            return PaymentOptionsResult(options=[], hardship_option=None, refinance_options=[], escalate=True)
        raw = payment_options_overdue(overdue_amount, pol, today)
        return PaymentOptionsResult(
            options=[o for o in raw if not o.hardship],
            hardship_option=next((o for o in raw if o.hardship), None),
            refinance_options=[],
        )
    if mode == "card_preventive":
        main, refi = payment_options_card_preventive(total_balance, minimum_payment, policy_opts, today)
        return PaymentOptionsResult(options=main, hardship_option=None, refinance_options=refi)
    if mode == "promise":
        try:
            raw = payment_options_promise(overdue_amount, promise_date, policy_opts, today)
        except ValueError as exc:
            if str(exc) == "promise_outside_window":
                raise
            raise
        return PaymentOptionsResult(
            options=[o for o in raw if o.kind != "promise"],
            hardship_option=None,
            refinance_options=[],
            promise_option=next((o for o in raw if o.kind == "promise"), None),
        )
    return PaymentOptionsResult(options=[], hardship_option=None, refinance_options=[])


# Backward-compatible helper for tests that import payment_options directly.
def payment_options(overdue_amount: int, policy: Policy, today: date) -> list[PlanOption]:
    return payment_options_overdue(overdue_amount, policy, today)
