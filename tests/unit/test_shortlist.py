"""The shortlist email rules: the schedule, DST, and which few jobs are picked."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from pv_domain.shortlist import (
    ELIGIBILITY_SENTENCES,
    MAX_ITEMS,
    Candidate,
    Schedule,
    ScheduleError,
    clean_schedule,
    describe_schedule,
    is_candidate,
    next_run,
    reason_for,
    select_shortlist,
    valid_timezone,
)

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)  # a Monday


def good(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "frequency": "weekly",
        "weekday": 0,
        "hour": 8,
        "timezone": "UTC",
        "max_items": 5,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------- cleaning


def test_a_good_schedule_is_accepted() -> None:
    s = clean_schedule(
        good(frequency="daily", weekday=3, hour=18, timezone="Asia/Kolkata", max_items=3)
    )
    assert s == Schedule("daily", 3, 18, "Asia/Kolkata", 3)


def test_the_number_of_jobs_defaults() -> None:
    raw = good()
    del raw["max_items"]
    assert clean_schedule(raw).max_items == 5


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"frequency": "hourly"}, "frequency"),
        ({"frequency": None}, "frequency"),
        ({"weekday": 7}, "weekday"),
        ({"weekday": -1}, "weekday"),
        ({"weekday": "1"}, "weekday"),
        ({"weekday": True}, "weekday"),
        ({"hour": 24}, "hour"),
        ({"hour": -1}, "hour"),
        ({"hour": 8.5}, "hour"),
        ({"hour": None}, "hour"),
        ({"hour": False}, "hour"),
        ({"timezone": "Mars/Base"}, "timezone"),
        ({"timezone": ""}, "timezone"),
        ({"timezone": "../../etc/passwd"}, "timezone"),
        ({"timezone": "/etc/localtime"}, "timezone"),
        ({"timezone": "x" * 80}, "timezone"),
        ({"timezone": 5}, "timezone"),
        ({"max_items": 0}, "max_items"),
        ({"max_items": 11}, "max_items"),
        ({"max_items": True}, "max_items"),
    ],
)
def test_bad_schedules_name_the_field(changes: dict[str, object], field: str) -> None:
    with pytest.raises(ScheduleError) as error:
        clean_schedule(good(**changes))
    assert field in error.value.fields and error.value.fields[field]


def test_every_problem_is_reported_at_once() -> None:
    with pytest.raises(ScheduleError) as error:
        clean_schedule({"frequency": "x", "hour": 99, "timezone": "nope", "max_items": 0})
    assert set(error.value.fields) == {"frequency", "hour", "timezone", "max_items"}


def test_time_zone_names() -> None:
    assert (
        valid_timezone("UTC")
        and valid_timezone("America/New_York")
        and valid_timezone("Asia/Kolkata")
    )
    assert not valid_timezone("") and not valid_timezone("..") and not valid_timezone("a/../b")


# --------------------------------------------------------------------- when it is due


def test_daily_runs_today_if_the_hour_has_not_come_and_tomorrow_if_it_has() -> None:
    s = Schedule("daily", 0, 8, "UTC")
    assert next_run(datetime(2026, 11, 2, 7, 59, tzinfo=UTC), s) == datetime(
        2026, 11, 2, 8, 0, tzinfo=UTC
    )
    assert next_run(datetime(2026, 11, 2, 8, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 3, 8, 0, tzinfo=UTC
    )  # strictly after
    assert next_run(datetime(2026, 11, 2, 9, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 3, 8, 0, tzinfo=UTC
    )


def test_weekly_runs_on_the_chosen_day() -> None:
    s = Schedule("weekly", 4, 8, "UTC")  # Friday
    assert next_run(T0, s) == datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    assert next_run(datetime(2026, 11, 6, 7, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 6, 8, 0, tzinfo=UTC
    )
    assert next_run(datetime(2026, 11, 6, 9, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 13, 8, 0, tzinfo=UTC
    )


def test_the_hour_is_on_the_persons_own_clock() -> None:
    s = Schedule("daily", 0, 8, "Asia/Kolkata")  # UTC+5:30, no daylight saving
    assert next_run(datetime(2026, 11, 2, 0, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 2, 2, 30, tzinfo=UTC
    )
    s = Schedule("daily", 0, 8, "America/Los_Angeles")  # UTC-8 in November
    assert next_run(datetime(2026, 11, 2, 0, 0, tzinfo=UTC), s) == datetime(
        2026, 11, 2, 16, 0, tzinfo=UTC
    )


def test_the_local_day_decides_the_weekday_not_the_utc_day() -> None:
    # Monday 8 in Auckland is Sunday in UTC.
    s = Schedule("weekly", 0, 8, "Pacific/Auckland")
    run = next_run(datetime(2026, 11, 2, 0, 0, tzinfo=UTC), s)
    local = run.astimezone(ZoneInfo("Pacific/Auckland"))
    assert (local.weekday(), local.hour) == (0, 8)
    assert run.weekday() == 6  # Sunday in UTC


def test_weekly_keeps_the_local_hour_across_a_change_of_clocks() -> None:
    s = Schedule("weekly", 0, 8, "America/New_York")
    zone = ZoneInfo("America/New_York")
    after = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)
    seen: list[datetime] = []
    for _ in range(4):  # Mondays across the end of daylight saving on 1 November
        after = next_run(after, s)
        seen.append(after)
    assert [d.astimezone(zone).hour for d in seen] == [8, 8, 8, 8]
    assert {d.astimezone(zone).weekday() for d in seen} == {0}
    assert seen[0].hour != seen[-1].hour  # the UTC hour moved by one


def test_a_local_time_that_does_not_exist_runs_after_the_gap() -> None:
    s = Schedule("daily", 0, 2, "America/New_York")  # 2:00 does not exist on 8 March 2026
    run = next_run(datetime(2026, 3, 8, 5, 0, tzinfo=UTC), s)  # midnight local, before the gap
    local = run.astimezone(ZoneInfo("America/New_York"))
    assert local.date().isoformat() == "2026-03-08" and local.hour in (3, 1, 2)
    assert run > datetime(2026, 3, 8, 5, 0, tzinfo=UTC)


def test_a_local_time_that_happens_twice_runs_the_first_time() -> None:
    s = Schedule("daily", 0, 1, "America/New_York")  # 1:00 happens twice on 1 November 2026
    run = next_run(datetime(2026, 11, 1, 3, 0, tzinfo=UTC), s)  # 23:00 local on 31 October
    assert run == datetime(2026, 11, 1, 5, 0, tzinfo=UTC)  # the first 1:00, in daylight time


@pytest.mark.parametrize(
    "zone",
    [
        "UTC",
        "Asia/Kolkata",
        "America/New_York",
        "Europe/London",
        "Pacific/Auckland",
        "Australia/Lord_Howe",
    ],
)
@pytest.mark.parametrize("frequency", ["daily", "weekly"])
def test_the_next_run_is_always_after_now_and_never_too_far_away(zone: str, frequency: str) -> None:
    s = Schedule(frequency, 2, 3, zone)
    after = datetime(2026, 1, 1, tzinfo=UTC)
    for step in range(0, 24 * 400, 17):  # every 17 hours for more than a year
        now = after + timedelta(hours=step)
        run = next_run(now, s)
        assert run > now
        assert run - now <= timedelta(days=8 if frequency == "weekly" else 2)


def test_running_from_a_run_gives_the_following_one_with_no_gaps_or_repeats() -> None:
    s = Schedule("weekly", 0, 8, "Europe/London")
    run = next_run(T0, s)
    following = next_run(run, s)
    assert following - run in (
        timedelta(days=7),
        timedelta(days=7, hours=1),
        timedelta(days=7, hours=-1),
    )


def test_a_time_with_no_zone_is_refused() -> None:
    with pytest.raises(ValueError):
        next_run(datetime(2026, 11, 2, 9, 0), Schedule())


def test_the_schedule_is_described_in_words() -> None:
    assert describe_schedule(Schedule("daily", 0, 8, "UTC")) == "Every day at 08:00 (UTC)"
    assert (
        describe_schedule(Schedule("weekly", 4, 18, "Asia/Kolkata"))
        == "Every Friday at 18:00 (Asia/Kolkata)"
    )


# --------------------------------------------------------------------- who is in it


def cand(id_: str, **kw: object) -> Candidate:
    base: dict[str, object] = {
        "id": id_, "title": f"Job {id_}", "company": "Acme", "location": "Pune", "work_mode": "remote",
        "eligibility": "eligible", "band": "strong", "state": "new", "created_at": T0,
    }  # fmt: skip
    base.update(kw)
    return Candidate(**base)  # type: ignore[arg-type]


def ids(items: list[Candidate]) -> list[str]:
    return [c.id for c in items]


def test_only_open_jobs_with_a_good_fit_and_nothing_in_the_way_are_candidates() -> None:
    assert is_candidate(cand("a"))
    assert is_candidate(cand("a", band="good", state="saved"))
    assert is_candidate(cand("a", state="approved_for_prep", eligibility="uncertain"))
    assert is_candidate(cand("a", eligibility="requires_user_input"))
    for bad in (
        {"state": "dismissed"}, {"state": "applied"}, {"state": "archived"},
        {"band": "review"}, {"band": "not_recommended"}, {"band": "not_eligible"}, {"band": None},
        {"eligibility": "not_eligible"}, {"eligibility": None},
    ):  # fmt: skip
        assert not is_candidate(cand("a", **bad)), bad


def test_a_job_in_an_earlier_email_is_never_sent_again() -> None:
    assert ids(select_shortlist([cand("a"), cand("b")], already_sent={"a"}, limit=5)) == ["b"]


def test_ranking_fit_then_clarity_then_saved_then_newest() -> None:
    day = lambda n: T0 + timedelta(days=n)  # noqa: E731
    pool = [
        cand("good-new", band="good", created_at=day(9)),
        cand("strong-unsure", eligibility="uncertain", created_at=day(8)),
        cand("strong-old", created_at=day(1)),
        cand("strong-new", created_at=day(5)),
        cand("strong-saved-old", state="saved", created_at=day(0)),
        cand("strong-needs-answer", eligibility="requires_user_input", created_at=day(7)),
    ]
    assert ids(select_shortlist(pool, already_sent=set(), limit=10)) == [
        "strong-saved-old",
        "strong-new",
        "strong-old",
        "strong-unsure",
        "strong-needs-answer",
        "good-new",
    ]


def test_the_limit_is_kept_between_one_and_ten() -> None:
    pool = [cand(f"{i:02d}") for i in range(15)]
    assert len(select_shortlist(pool, already_sent=set(), limit=3)) == 3
    assert len(select_shortlist(pool, already_sent=set(), limit=99)) == MAX_ITEMS
    assert len(select_shortlist(pool, already_sent=set(), limit=0)) == 1


def test_the_same_jobs_give_the_same_list_whatever_order_they_come_in() -> None:
    pool = [cand(c, created_at=T0) for c in "dbeacf"]  # all tie on everything but the id
    forward = ids(select_shortlist(pool, already_sent=set(), limit=10))
    backward = ids(select_shortlist(list(reversed(pool)), already_sent=set(), limit=10))
    assert forward == backward == sorted(forward)


def test_nothing_worth_sending_is_an_empty_list() -> None:
    assert select_shortlist([cand("a", band="review")], already_sent=set(), limit=5) == []
    assert select_shortlist([], already_sent=set(), limit=5) == []


def test_the_reason_says_the_band_the_support_and_the_eligibility() -> None:
    reason = reason_for(cand("a"), "9 of 11 required requirements supported (8 fully, 1 partly).")
    assert (
        reason
        == "Strong match: 9 of 11 required requirements supported (8 fully, 1 partly). Nothing stands in your way."
    )
    assert reason_for(cand("a", band="good", eligibility="uncertain"), "").startswith("Good match.")
    assert ELIGIBILITY_SENTENCES["uncertain"] in reason_for(cand("a", eligibility="uncertain"), "x")
