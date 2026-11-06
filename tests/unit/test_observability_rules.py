"""Checkpoint 3.5: alert rules, request statistics, and the plain words for a run.

Every alert rule is tested at its edge (just under, at and over its threshold) and a missing
measurement is shown not to fire anything.
"""

import pytest

from pv_api.metrics import RequestStats
from pv_domain.alerts import (
    CRITICAL,
    WARNING,
    Alert,
    Snapshot,
    SourceHealth,
    Thresholds,
    evaluate,
    worst,
)
from pv_domain.run_explain import FAILURES, explain_failure, step_label, subject_for


def keys(snapshot: Snapshot, limits: Thresholds | None = None) -> list[str]:
    return [a.key for a in evaluate(snapshot, limits)]


def only(snapshot: Snapshot, key: str, limits: Thresholds | None = None) -> Alert:
    found = [a for a in evaluate(snapshot, limits) if a.key == key]
    assert len(found) == 1, [a.key for a in evaluate(snapshot, limits)]
    return found[0]


# ------------------------------------------------------------------ a healthy system


def test_a_healthy_snapshot_raises_nothing() -> None:
    assert evaluate(Snapshot()) == ()
    assert worst(()) == "ok"


def test_nothing_measured_is_not_read_as_trouble() -> None:
    quiet = Snapshot(requests=None, server_errors=None, p95_ms=None, oldest_waiting_seconds=None)
    assert evaluate(quiet) == ()


# ------------------------------------------------------------------ the basics


def test_a_down_database_and_a_behind_migration_are_critical() -> None:
    assert only(Snapshot(database_ok=False), "database_down").severity == CRITICAL
    assert only(Snapshot(migrations="behind"), "migrations_behind").severity == CRITICAL
    assert "migrations_behind" not in keys(Snapshot(migrations="unknown"))


def test_no_worker_is_critical_only_when_work_is_waiting() -> None:
    assert only(Snapshot(workers_alive=0, queue_waiting=3), "no_worker").severity == CRITICAL
    assert only(Snapshot(workers_alive=0, queue_waiting=0), "no_worker").severity == WARNING
    assert "no_worker" not in keys(Snapshot(workers_alive=1, workers_stale=2))


# ------------------------------------------------------------------ the queue


@pytest.mark.parametrize(
    ("age", "expected"),
    [(299, None), (300, WARNING), (1799, WARNING), (1800, CRITICAL), (7200, CRITICAL)],
)
def test_a_stale_queue_has_two_levels(age: int, expected: str | None) -> None:
    snapshot = Snapshot(queue_waiting=4, oldest_waiting_seconds=age)
    found = [a for a in evaluate(snapshot) if a.key == "queue_stale"]
    assert (found[0].severity if found else None) == expected


def test_a_stale_queue_with_no_worker_is_the_worker_alert_not_two() -> None:
    snapshot = Snapshot(workers_alive=0, queue_waiting=4, oldest_waiting_seconds=9000)
    assert keys(snapshot) == ["no_worker"]


def test_stuck_tasks_and_dead_letters() -> None:
    assert only(Snapshot(stuck_tasks=2), "stuck_tasks").severity == WARNING
    letters = only(Snapshot(dead_letters_24h=3, dead_letters_total=9), "dead_letters")
    assert "3 tasks" in letters.detail and "9 in all" in letters.detail
    assert "dead_letters" not in keys(Snapshot(dead_letters_24h=0, dead_letters_total=9))


# ------------------------------------------------------------------ sources


def test_a_source_that_is_paused_or_keeps_failing_is_named() -> None:
    paused = SourceHealth("greenhouse", "Greenhouse", True, True, 5)
    failing = SourceHealth("lever", "Lever", True, False, 3)
    fine = SourceHealth("ashby", "Ashby", True, False, 2)
    off = SourceHealth("adzuna", "Adzuna", False, True, 9)
    found = evaluate(Snapshot(sources=(paused, failing, fine, off)))
    assert [a.key for a in found] == ["source_breaker_greenhouse", "source_failing_lever"]
    assert "Greenhouse" in found[0].title and "Lever" in found[1].title


def test_the_failure_streak_threshold_can_be_set() -> None:
    source = SourceHealth("lever", "Lever", True, False, 2)
    assert keys(Snapshot(sources=(source,))) == []
    assert keys(Snapshot(sources=(source,)), Thresholds(source_failure_streak=2)) == [
        "source_failing_lever"
    ]


# ------------------------------------------------------------------ the model provider


def test_model_errors_need_enough_calls_and_a_high_rate() -> None:
    assert "llm_errors" not in keys(Snapshot(llm_calls_24h=9, llm_errors_24h=9))  # too few calls
    assert "llm_errors" not in keys(Snapshot(llm_calls_24h=100, llm_errors_24h=24))  # under 25%
    assert only(Snapshot(llm_calls_24h=100, llm_errors_24h=25), "llm_errors").severity == WARNING


def test_spend_has_no_alert_until_a_ceiling_is_set() -> None:
    assert evaluate(Snapshot(llm_cost_24h_usd=1_000.0)) == ()


@pytest.mark.parametrize(
    ("spend", "expected"), [(7.99, None), (8.0, WARNING), (9.99, WARNING), (10.0, CRITICAL)]
)
def test_spend_against_a_ceiling(spend: float, expected: str | None) -> None:
    limits = Thresholds(daily_spend_ceiling_usd=10.0)
    found = [a for a in evaluate(Snapshot(llm_cost_24h_usd=spend), limits) if "spend" in a.key]
    assert (found[0].severity if found else None) == expected
    if found:
        assert "$10.00" in found[0].detail


# ------------------------------------------------------------------ the API


def test_api_errors_need_enough_requests_and_a_high_rate() -> None:
    assert "api_errors" not in keys(Snapshot(requests=49, server_errors=49))  # too few requests
    assert "api_errors" not in keys(Snapshot(requests=100, server_errors=4))  # under 5%
    assert only(Snapshot(requests=100, server_errors=5), "api_errors").severity == CRITICAL


def test_a_slow_api_needs_enough_requests() -> None:
    assert "api_slow" not in keys(Snapshot(requests=10, p95_ms=9000))
    assert "api_slow" not in keys(Snapshot(requests=100, p95_ms=2999))
    assert only(Snapshot(requests=100, p95_ms=3000), "api_slow").severity == WARNING


# ------------------------------------------------------------------ security


def test_failed_sign_ins_and_wrong_origins() -> None:
    assert "auth_failures" not in keys(Snapshot(auth_failures_1h=49))
    assert only(Snapshot(auth_failures_1h=50), "auth_failures").severity == WARNING
    assert "origin_rejections" not in keys(Snapshot(origin_rejections_1h=19))
    assert only(Snapshot(origin_rejections_1h=20), "origin_rejections").severity == WARNING


# ------------------------------------------------------------------ the whole


def test_alerts_come_critical_first_then_by_key_and_each_has_an_action_and_a_runbook() -> None:
    snapshot = Snapshot(
        database_ok=False,
        stuck_tasks=1,
        dead_letters_24h=1,
        auth_failures_1h=60,
        requests=100,
        server_errors=50,
        sources=(SourceHealth("a", "A", True, True, 4),),
    )
    found = evaluate(snapshot)
    severities = [a.severity for a in found]
    assert severities == sorted(severities, key=lambda s: 0 if s == CRITICAL else 1)
    assert worst(found) == CRITICAL
    for alert in found:
        assert alert.title and alert.detail and alert.action
        assert alert.runbook == "operations/runbooks/alerts.md"
    assert evaluate(snapshot) == evaluate(snapshot)  # the same snapshot, the same alerts


def test_only_a_warning_makes_the_headline_a_warning() -> None:
    assert worst(evaluate(Snapshot(stuck_tasks=1))) == WARNING


# ------------------------------------------------------------------ request statistics


def test_request_stats_count_errors_and_percentiles() -> None:
    stats = RequestStats()
    for i in range(100):
        stats.record(500 if i < 5 else 404 if i < 10 else 200, float(i + 1), now=1000.0)
    snap = stats.snapshot(now=1000.0)
    assert snap.requests == 100 and snap.server_errors == 5 and snap.client_errors == 5
    assert snap.p50_ms == 50 and snap.p95_ms == 95


def test_request_stats_forget_old_requests_and_cap_memory() -> None:
    stats = RequestStats(window_seconds=60, max_samples=10)
    stats.record(500, 10.0, now=0.0)
    stats.record(200, 20.0, now=100.0)
    snap = stats.snapshot(now=110.0)
    assert snap.requests == 1 and snap.server_errors == 0
    for i in range(50):
        stats.record(200, 1.0, now=110.0 + i * 0.01)
    assert stats.snapshot(now=111.0).requests == 10  # bounded


def test_no_requests_means_none_not_zero() -> None:
    snap = RequestStats().snapshot()
    assert snap.requests == 0 and snap.p50_ms is None and snap.p95_ms is None


# ------------------------------------------------------------------ words for a run


def test_a_subject_has_a_label_and_a_page_when_it_has_one() -> None:
    assert subject_for("job_posting", "abc") == ("A job", "/opportunities/abc")
    assert subject_for("resume_document", "x") == ("A resume you made in the studio", "/studio")
    assert subject_for("job_posting", None) == ("A job", None)
    assert subject_for("surprise", "x") == (None, None)
    assert subject_for(None, None) == (None, None)


def test_a_failure_says_what_happened_and_what_to_do() -> None:
    what, todo = explain_failure("JOB_ANALYSIS_FAILED", True)
    assert "evidence check" in what and "again" in todo and "not be tried again" not in todo
    _what, no_retry = explain_failure("JOB_ANALYSIS_FAILED", False)
    assert no_retry.endswith("It will not be tried again by itself.")


def test_an_unknown_failure_gets_a_safe_sentence_and_never_the_raw_class() -> None:
    what, todo = explain_failure("SomeNewThing", True)
    assert what == "This run did not finish." and "SomeNewThing" not in what + todo
    assert explain_failure(None, True)[0] == "This run did not finish."


def test_every_known_failure_has_both_halves() -> None:
    for what, todo in FAILURES.values():
        assert what.endswith(".") and todo.endswith(".")


def test_steps_have_readable_labels() -> None:
    assert step_label("render_pdf") == "Make the PDF"
    assert step_label("Extract requirements") == "Extract requirements"
    assert step_label("some_new_step") == "Some new step"
    assert step_label("") == "Step"
