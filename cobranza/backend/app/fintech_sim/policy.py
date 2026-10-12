"""Avanza Crédito's credit policy: the only source of payment amounts and dates.

The agent never computes a number; it reads what this module returns. There is
no discount path here, so a discount the customer asks for cannot exist.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.fintech_sim.holidays import next_business_day

OptionKind = Literal["full", "installments", "hardship"]


@dataclass(frozen=True)
class Policy:
    max_installments: int
    min_installment_cop: int
    first_payment_max_days: int
    hardship_enabled: bool
    hardship_installments: int
    hardship_grace_days: int


@dataclass(frozen=True)
class PlanOption:
    kind: OptionKind
    installments: int
    installment_amount: int
    last_installment_amount: int
    total_amount: int
    first_due_date: date
    hardship: bool


def _split(total: int, parts: int) -> tuple[int, int]:
    """Equal installments rounded up to the nearest 100 COP; the last absorbs the remainder."""
    installment = math.ceil(total / parts / 100) * 100
    last = total - installment * (parts - 1)
    return installment, last


def payment_options(overdue_amount: int, policy: Policy, today: date) -> list[PlanOption]:
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
