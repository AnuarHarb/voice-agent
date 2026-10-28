"""Amortization helpers for spoken commercial offers."""

import math


def monthly_payment(amount: int, rate_ea: float, term_months: int) -> int:
    if term_months <= 0:
        return amount
    monthly = (1 + rate_ea / 100) ** (1 / 12) - 1
    if monthly <= 0:
        return math.ceil(amount / term_months)
    factor = (1 + monthly) ** term_months
    payment = amount * monthly * factor / (factor - 1)
    return int(math.ceil(payment / 100) * 100)


def total_cost(installment: int, term_months: int) -> int:
    return installment * term_months
