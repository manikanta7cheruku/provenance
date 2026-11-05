"""Checkpoint 3.3: the rules of plans and quotas. What a limit means, the month, the decision, a bad
plan row, and the sentences a person reads."""

from datetime import UTC, date, datetime

import pytest

from pv_domain.billing import DisabledPayments
from pv_domain.entitlements import (
    SEED_PLANS,
    UNIT_ANALYSIS,
    UNIT_LABELS,
    UNITS,
    decide,
    limits_as_data,
    limits_from_row,
    meter_state,
    next_reset,
    percent,
    period_start,
    quota_message,
    resume_limit_message,
)


def at(y: int, m: int, d: int, hour: int = 12) -> datetime:
    return datetime(y, m, d, hour, tzinfo=UTC)


# ------------------------------------------------------------------ the month


def test_the_period_is_the_calendar_month_in_utc() -> None:
    assert period_start(at(2026, 11, 5)) == date(2026, 11, 1)
    assert period_start(at(2026, 11, 30, 23)) == date(2026, 11, 1)
    assert period_start(at(2026, 12, 1, 0)) == date(2026, 12, 1)


def test_a_late_evening_elsewhere_is_judged_by_utc() -> None:
    # 00:30 on 1 December in Kolkata is still 19:00 on 30 November in UTC.
    from datetime import timedelta, timezone

    kolkata = timezone(timedelta(hours=5, minutes=30))
    assert period_start(datetime(2026, 12, 1, 0, 30, tzinfo=kolkata)) == date(2026, 11, 1)


def test_the_reset_is_the_first_of_next_month() -> None:
    assert next_reset(at(2026, 11, 5)) == at(2026, 12, 1, 0)
    assert next_reset(at(2026, 12, 31)) == at(2027, 1, 1, 0)
    assert next_reset(at(2026, 2, 28)) == at(2026, 3, 1, 0)
    assert next_reset(at(2028, 2, 29)) == at(2028, 3, 1, 0)
    assert next_reset(at(2026, 1, 31)) == at(2026, 2, 1, 0)


# ------------------------------------------------------------------ the decision


def test_a_limit_allows_up_to_and_including_it() -> None:
    assert decide(3, 0).allowed and decide(3, 2).allowed
    assert not decide(3, 3).allowed and not decide(3, 4).allowed
    assert (
        decide(3, 2).remaining == 1 and decide(3, 3).remaining == 0 and decide(3, 9).remaining == 0
    )


def test_no_limit_always_allows() -> None:
    result = decide(None, 10_000)
    assert result.allowed and result.remaining is None and result.limit is None


def test_a_zero_limit_allows_nothing() -> None:
    assert not decide(0, 0).allowed


def test_an_amount_larger_than_one_is_checked_whole() -> None:
    assert decide(5, 3, amount=2).allowed
    assert not decide(5, 4, amount=2).allowed


@pytest.mark.parametrize(
    ("limit", "used", "state", "pct"),
    [
        (10, 0, "ok", 0),
        (10, 7, "ok", 70),
        (10, 8, "near", 80),
        (10, 9, "near", 90),
        (10, 10, "reached", 100),
        (10, 12, "reached", 100),
        (0, 0, "reached", 100),
        (None, 50, "ok", 0),
    ],
)
def test_the_meter_says_ok_near_or_reached(
    limit: int | None, used: int, state: str, pct: int
) -> None:
    assert meter_state(limit, used) == state
    assert percent(limit, used) == pct


# ------------------------------------------------------------------ plans as data


def test_the_seed_plans_grow_and_cover_every_unit() -> None:
    free, starter, pro = SEED_PLANS
    assert [p.id for p in SEED_PLANS] == ["free", "starter", "pro"]
    for plan in SEED_PLANS:
        assert set(plan.units) == set(UNITS)
        assert all(v is not None and v > 0 for v in plan.units.values())
    for unit in UNITS:
        assert free.units[unit] < starter.units[unit] < pro.units[unit]  # type: ignore[operator]
    assert free.resumes == 1 and free.resumes < starter.resumes < pro.resumes
    assert free.exports_per_resume == 5


def test_a_plan_round_trips_through_its_stored_data() -> None:
    for plan in SEED_PLANS:
        assert limits_from_row(plan.id, plan.label, limits_as_data(plan)) == plan


def test_a_bad_row_can_only_be_stricter() -> None:
    plan = limits_from_row(
        "x",
        "X",
        {
            "units": {UNIT_ANALYSIS: "lots", "discovery_run": -5},
            "resumes": "many",
            "exports_per_resume": None,
        },
    )
    assert plan.units[UNIT_ANALYSIS] == 0 and plan.units["discovery_run"] == 0
    assert plan.units["url_analysis"] == 0 and plan.units["material_generation"] == 0
    assert plan.resumes == 0 and plan.exports_per_resume == 0
    empty = limits_from_row("y", "Y", {})
    assert all(v == 0 for v in empty.units.values()) and empty.resumes == 0


def test_none_in_a_row_means_no_limit_on_purpose() -> None:
    plan = limits_from_row(
        "big", "Big", {"units": {u: None for u in UNITS}, "resumes": 5, "exports_per_resume": 5}
    )
    assert all(v is None for v in plan.units.values())


# ------------------------------------------------------------------ the words


def test_the_quota_sentence_says_what_was_used_what_is_allowed_and_when_it_restarts() -> None:
    message = quota_message(UNIT_ANALYSIS, "Free", 30, 30, at(2026, 12, 1, 0))
    assert "30 of the 30 checks" in message and "Free plan" in message
    assert "1 December" in message and "Nothing was changed" in message
    assert "05 " not in quota_message(UNIT_ANALYSIS, "Free", 1, 1, at(2026, 12, 5, 0))


def test_a_plan_that_does_not_include_something_says_so() -> None:
    assert "does not include" in quota_message(UNIT_ANALYSIS, "Odd", 0, 0, at(2026, 12, 1, 0))


def test_every_unit_has_a_label_and_a_noun() -> None:
    for unit in UNITS:
        label, noun = UNIT_LABELS[unit]
        assert label and noun


def test_the_resume_sentence_is_singular_or_plural() -> None:
    assert (
        resume_limit_message("Free", 1)
        == "The Free plan keeps 1 resume. Delete one first to start another."
    )
    assert "3 resumes" in resume_limit_message("Starter", 3)


# ------------------------------------------------------------------ payments stay off


def test_payments_are_off_and_say_so() -> None:
    payments = DisabledPayments()
    assert payments.enabled is False and payments.name == "none"
    for result in (
        payments.start_checkout(user_id="u", plan_id="pro"),
        payments.cancel(user_id="u"),
    ):
        assert (
            result.available is False
            and result.url is None
            and "Nothing is charged" in result.message
        )
