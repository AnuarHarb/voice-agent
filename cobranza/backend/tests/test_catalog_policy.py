from datetime import date

import pytest

from app.fintech_sim.policy import payment_options_for_account


def test_card_preventive_refi_separate():
    result = payment_options_for_account(
        mode="card_preventive",
        overdue_amount=0,
        total_balance=2_000_000,
        minimum_payment=380_000,
        days_past_due=0,
        policy_opts={"refinance_min_balance_cop": 500_000, "refinance_terms": [6, 12]},
        today=date(2026, 10, 13),
    )
    assert [o.kind for o in result.options] == ["minimum", "full"]
    assert len(result.refinance_options) == 2


def test_vehicle_escalates_after_sixty_days():
    result = payment_options_for_account(
        mode="overdue",
        overdue_amount=1_000_000,
        total_balance=5_000_000,
        minimum_payment=0,
        days_past_due=75,
        policy_opts={
            "max_installments": 2,
            "min_installment_cop": 150_000,
            "first_payment_max_days": 5,
            "hardship_enabled": False,
            "escalate_when_days_past_due_gt": 60,
        },
        today=date(2026, 10, 13),
    )
    assert result.escalate is True and result.options == []


def test_promise_outside_window():
    with pytest.raises(ValueError, match="promise_outside_window"):
        payment_options_for_account(
            mode="promise",
            overdue_amount=100_000,
            total_balance=100_000,
            minimum_payment=0,
            days_past_due=5,
            policy_opts={"promise_max_days": 7},
            today=date(2026, 10, 13),
            promise_date=date(2026, 10, 22),
        )
