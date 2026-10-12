from datetime import date

from app.fintech_sim.holidays import colombian_holidays, next_business_day
from app.fintech_sim.policy import Policy, payment_options
from app.integration.formatting import date_text, money_text

AVANZA = Policy(max_installments=3, min_installment_cop=150000, first_payment_max_days=5,
                hardship_enabled=True, hardship_installments=6, hardship_grace_days=30)
NEXO = Policy(max_installments=2, min_installment_cop=200000, first_payment_max_days=3,
              hardship_enabled=False, hardship_installments=1, hardship_grace_days=0)


def test_colombian_holidays_2026():
    expected = {
        date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3),
        date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29),
        date(2026, 7, 20), date(2026, 8, 7), date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2),
        date(2026, 11, 16), date(2026, 12, 8), date(2026, 12, 25),
    }
    assert colombian_holidays(2026) == expected


def test_next_business_day_skips_sunday_and_holiday():
    assert next_business_day(date(2026, 10, 11)) == date(2026, 10, 13)  # Sunday, then Día de la Raza
    assert next_business_day(date(2026, 10, 17)) == date(2026, 10, 17)  # Saturday is a business day


def test_avanza_options_come_only_from_policy():
    options = payment_options(1_200_000, AVANZA, today=date(2026, 10, 11))
    assert [o.kind for o in options] == ["full", "installments", "hardship"]
    full, installments, hardship = options
    assert (full.installments, full.total_amount, full.first_due_date) == (1, 1_200_000, date(2026, 10, 16))
    assert (installments.installments, installments.installment_amount) == (3, 400_000)
    assert installments.first_due_date == date(2026, 10, 19)  # Oct 18 is a Sunday
    assert (hardship.installments, hardship.installment_amount, hardship.hardship) == (6, 200_000, True)
    assert hardship.first_due_date == date(2026, 11, 10)
    # No option ever charges less than what is owed: there is no discount path.
    assert all(o.total_amount == 1_200_000 for o in options)
    assert all(o.installment_amount * (o.installments - 1) + o.last_installment_amount == o.total_amount
               for o in options)


def test_uneven_split_last_installment_absorbs_remainder():
    options = payment_options(450_000, AVANZA, today=date(2026, 10, 13))
    installments = next(o for o in options if o.kind == "installments")
    assert installments.installments == 3
    assert installments.installment_amount * 2 + installments.last_installment_amount == 450_000

    options = payment_options(1_000_001, AVANZA, today=date(2026, 10, 13))
    plan = next(o for o in options if o.kind == "installments")
    assert (plan.installment_amount, plan.last_installment_amount) == (333_400, 333_201)


def test_nexo_policy_has_no_hardship_and_two_installments():
    options = payment_options(800_000, NEXO, today=date(2026, 10, 13))
    assert [o.kind for o in options] == ["full", "installments"]
    assert options[1].installments == 2


def test_small_debt_only_offers_full_payment():
    assert [o.kind for o in payment_options(200_000, NEXO, today=date(2026, 10, 13))] == ["full"]
    assert payment_options(0, AVANZA, today=date(2026, 10, 13)) == []


def test_formatting_for_voice_and_audit():
    assert money_text(1_200_000) == "$1.200.000"
    assert date_text(date(2026, 10, 16)) == "viernes 16 de octubre"
    assert date_text(date(2026, 10, 16), "en") == "Friday, October 16"
