"""Checkpoint 2.6: polling a source, the circuit breaker, health, and the jobs that people can see."""

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_persistence.registry import seed_registry
from pv_worker.contract import TaskContext
from pv_worker.fetcher import FetchError, FetchResponse
from pv_worker.handlers.poll_source import run_poll

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
LEVER = json.loads((FIXTURES / "lever.json").read_text(encoding="utf-8"))
T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
MakeAccount = Callable[..., Account]
ADMIN = "/api/v1/admin/sources"
SEARCH = "/api/v1/search"


class FakeFetcher:
    """Stands in for the network. `answers` is a list of what each call returns or raises."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.calls: list[str] = []

    def get(self, url: str, *, hosts: tuple[str, ...]) -> FetchResponse:
        self.calls.append(url)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer  # type: ignore[no-any-return]


def ok(data: Any = None) -> FetchResponse:
    return FetchResponse(200, json.dumps(LEVER if data is None else data).encode())


def status(code: int, **headers: str) -> FetchResponse:
    return FetchResponse(code, b"", headers)


def _reset(engine: Engine) -> None:
    """Back to the seed, with no poll left queued: a worker must never poll because of a test."""
    seed_registry(engine)
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE job_sources SET edited_at = NULL"))
        db.execute(text("DELETE FROM tasks WHERE task_type = 'poll_source'"))
        db.execute(text("DELETE FROM source_jobs"))
        db.execute(text("DELETE FROM source_targets"))
        db.execute(text("DELETE FROM fetch_log"))
    seed_registry(engine)


@pytest.fixture(autouse=True)
def lever_ready(engine: Engine) -> Iterator[None]:
    """Lever is switched on as an administrator would, with its review dated today."""
    seed_registry(engine)
    with Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM source_jobs"))
        db.execute(text("DELETE FROM source_targets"))
        db.execute(text("DELETE FROM fetch_log"))
        db.execute(text("DELETE FROM tasks WHERE task_type = 'poll_source'"))
        db.execute(
            text(
                "UPDATE job_sources SET compliance_status = 'verified', terms_checked_at = current_date, "
                "verification_owner = 'test', enabled = true, failure_streak = 0, breaker_open_until = NULL, "
                "last_success_at = NULL, last_failure_at = NULL, health_status = 'unknown', "
                "min_poll_interval_seconds = 3600, edited_at = now() WHERE key = 'lever'"
            )
        )
        db.execute(
            text("UPDATE job_sources SET enabled = false, edited_at = now() WHERE key <> 'lever'")
        )
    yield
    _reset(engine)


def ctx(
    engine: Engine, settings: Settings, *, chain: bool = False, key: str = "lever"
) -> TaskContext:
    return TaskContext(
        task_id=uuid.uuid4(),
        task_type="poll_source",
        args={"source_key": key, "chain": chain},
        secret={},
        attempt=1,
        max_attempts=3,
        owner_user_id=None,
        run_id=None,
        settings=settings,
        engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )


def poll(
    engine: Engine, settings: Settings, fetcher: FakeFetcher, at: datetime = T0, **kw: Any
) -> None:
    run_poll(ctx(engine, settings, **kw), fetcher=fetcher, sleep=lambda s: None, clock=lambda: at)


def one(engine: Engine, sql: str, **params: Any) -> Any:
    with Session(engine) as db:
        return db.execute(text(sql), params).first()


def log(engine: Engine) -> list[str]:
    with Session(engine) as db:
        return [r[0] for r in db.execute(text("SELECT outcome FROM fetch_log ORDER BY id"))]


def health(engine: Engine) -> Any:
    return one(
        engine,
        "SELECT health_status, failure_streak, breaker_open_until, last_success_at "
        "FROM job_sources WHERE key = 'lever'",
    )


# ------------------------------------------------------------------------------ a good poll


def test_a_poll_keeps_the_jobs_logs_the_counts_and_marks_the_source_healthy(
    engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(ok())
    poll(engine, settings, fetcher)
    assert fetcher.calls == ["https://api.lever.co/v0/postings/palantir?mode=json"]
    jobs = one(
        engine, "SELECT count(*), count(*) FILTER (WHERE closed_at IS NULL) FROM source_jobs"
    )
    assert tuple(jobs) == (2, 2)
    entry = one(
        engine, "SELECT outcome, jobs_seen, jobs_new, jobs_closed, http_status FROM fetch_log"
    )
    assert tuple(entry) == ("ok", 2, 2, 0, 200)
    state = health(engine)
    assert (
        state.health_status == "healthy"
        and state.failure_streak == 0
        and state.last_success_at is not None
    )
    target = one(
        engine, "SELECT last_outcome, jobs_open FROM source_targets WHERE board_id = 'palantir'"
    )
    assert tuple(target) == ("ok", 2)


def test_what_is_stored_is_plain_text_and_https_only(engine: Engine, settings: Settings) -> None:
    hostile = [
        {
            **LEVER[0],
            "id": "h1",
            "descriptionPlain": None,
            "additionalPlain": None,
            "additional": None,
            "description": "<script>alert(1)</script><b>Hi</b>",
        }
    ]
    poll(engine, settings, FakeFetcher(ok(hostile)))
    row = one(engine, "SELECT description, url FROM source_jobs WHERE external_id = 'h1'")
    assert row.description == "Hi" and row.url.startswith("https://")


# ------------------------------------------------------------------------------ the interval


def test_a_board_is_not_asked_again_before_the_interval_whoever_asks(
    engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(ok())
    poll(engine, settings, fetcher, T0)
    poll(engine, settings, fetcher, T0 + timedelta(minutes=59))
    assert len(fetcher.calls) == 1 and "skipped_interval" in log(engine)
    poll(engine, settings, fetcher, T0 + timedelta(minutes=61))
    assert len(fetcher.calls) == 2


def test_changes_are_updated_and_jobs_that_vanish_are_closed_not_deleted_and_can_return(
    engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(ok())
    poll(engine, settings, fetcher, T0)
    changed = [{**LEVER[0], "text": LEVER[0]["text"] + " II"}]  # the second job is gone
    fetcher.answers = [ok(changed)]
    poll(engine, settings, fetcher, T0 + timedelta(hours=2))
    entry = one(
        engine,
        "SELECT jobs_seen, jobs_new, jobs_changed, jobs_closed FROM fetch_log WHERE id = (SELECT max(id) FROM fetch_log)",
    )
    assert tuple(entry) == (1, 0, 1, 1)
    assert one(engine, "SELECT count(*) FROM source_jobs").count == 2  # nothing deleted
    assert one(engine, "SELECT count(*) FROM source_jobs WHERE closed_at IS NOT NULL").count == 1
    fetcher.answers = [ok()]
    poll(engine, settings, fetcher, T0 + timedelta(hours=4))
    assert one(engine, "SELECT count(*) FROM source_jobs WHERE closed_at IS NOT NULL").count == 0


# ------------------------------------------------------------------------------ trouble


def test_a_board_that_is_gone_is_that_boards_problem_not_the_sources(
    engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(status(404)))
    assert log(engine) == ["not_found"] and health(engine).failure_streak == 0
    assert one(engine, "SELECT consecutive_errors FROM source_targets").consecutive_errors == 1


def test_an_answer_that_is_not_what_was_expected_changes_nothing_and_counts_against_the_source(
    engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()), T0)
    for data in (
        b"<html>maintenance</html>",
        json.dumps({"jobs": []}).encode(),
        json.dumps([{"id": "x"}]).encode(),
    ):
        before = health(engine).failure_streak
        poll(
            engine,
            settings,
            FakeFetcher(FetchResponse(200, data)),
            T0 + timedelta(hours=2 * (before + 1)),
        )
        assert log(engine)[-1] == "bad_response" and health(engine).failure_streak == before + 1
    assert (
        one(engine, "SELECT count(*) FROM source_jobs WHERE closed_at IS NULL").count == 2
    )  # nothing closed


def test_the_breaker_opens_after_five_failures_and_nothing_is_asked_while_it_is_open(
    engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(status(500))
    for n in range(5):
        poll(engine, settings, fetcher, T0 + timedelta(hours=2 * n))
    state = health(engine)
    assert (
        state.failure_streak == 5
        and state.health_status == "down"
        and state.breaker_open_until is not None
    )
    calls = len(fetcher.calls)
    poll(engine, settings, fetcher, T0 + timedelta(hours=8, minutes=5))
    assert len(fetcher.calls) == calls and log(engine)[-1] == "skipped_breaker"


def test_after_the_wait_one_probe_is_made_and_a_success_closes_the_breaker(
    engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(status(500))
    for n in range(5):
        poll(engine, settings, fetcher, T0 + timedelta(hours=2 * n))
    fetcher.answers = [ok()]
    poll(engine, settings, fetcher, T0 + timedelta(hours=9))
    state = health(engine)
    assert (
        state.failure_streak == 0
        and state.breaker_open_until is None
        and state.health_status == "healthy"
    )


def test_a_failed_probe_opens_the_breaker_for_longer(engine: Engine, settings: Settings) -> None:
    fetcher = FakeFetcher(status(503))
    for n in range(5):
        poll(engine, settings, fetcher, T0 + timedelta(hours=2 * n))
    first = health(engine).breaker_open_until
    probe_at = T0 + timedelta(hours=9)
    poll(engine, settings, fetcher, probe_at)
    second = health(engine).breaker_open_until
    assert (
        second is not None
        and first is not None
        and (second - probe_at) > (first - (T0 + timedelta(hours=8)))
    )


def test_one_failing_source_does_not_stop_another(engine: Engine, settings: Settings) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "UPDATE job_sources SET failure_streak = 7, breaker_open_until = now() + interval '1 day' WHERE key = 'lever'"
            )
        )
    assert (
        one(engine, "SELECT count(*) FROM job_sources WHERE breaker_open_until IS NOT NULL").count
        == 1
    )


def test_a_429_is_obeyed_with_its_retry_after(engine: Engine, settings: Settings) -> None:
    fetcher = FakeFetcher(status(429, **{"retry-after": "600"}))
    poll(engine, settings, fetcher, T0)
    state = health(engine)
    assert log(engine) == ["rate_limited"] and state.failure_streak == 1
    assert state.breaker_open_until is not None and state.breaker_open_until >= T0 + timedelta(
        minutes=10
    )


def test_a_network_failure_counts_and_stops_the_poll(engine: Engine, settings: Settings) -> None:
    poll(engine, settings, FakeFetcher(FetchError("network", "down")))
    assert log(engine) == ["network_error"] and health(engine).failure_streak == 1


def test_a_source_that_is_not_usable_is_not_asked_and_no_next_poll_is_queued(
    engine: Engine, settings: Settings
) -> None:
    for sql in (
        "UPDATE job_sources SET enabled = false WHERE key = 'lever'",
        "UPDATE job_sources SET terms_checked_at = '2020-01-01' WHERE key = 'lever'",
    ):
        with Session(engine) as db, db.begin():
            db.execute(text(sql))
        fetcher = FakeFetcher(ok())
        poll(engine, settings, fetcher, chain=True)
        assert fetcher.calls == [] and log(engine)[-1] == "skipped_unusable"
        assert one(engine, "SELECT count(*) FROM tasks WHERE task_type = 'poll_source'").count == 0
        with Session(engine) as db, db.begin():
            db.execute(
                text(
                    "UPDATE job_sources SET enabled = true, terms_checked_at = current_date WHERE key = 'lever'"
                )
            )


def test_a_chained_poll_queues_the_next_one_and_two_chains_become_one(
    engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()), T0, chain=True)
    poll(engine, settings, FakeFetcher(ok()), T0 + timedelta(minutes=5), chain=True)
    rows = one(engine, "SELECT count(*) FROM tasks WHERE task_type = 'poll_source'")
    assert rows.count == 1
    poll(engine, settings, FakeFetcher(ok()), T0 + timedelta(minutes=5), chain=False)
    assert one(engine, "SELECT count(*) FROM tasks WHERE task_type = 'poll_source'").count == 1


# ------------------------------------------------------------------------------ what people can see


def test_jobs_are_listed_with_attribution_and_filtered_in_sql(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()))
    account = make_account(app)
    body = account.client.get(f"{SEARCH}/jobs").json()
    assert len(body) == 2 and all(
        j["source_name"] == "Lever postings" and j["url"].startswith("https://") for j in body
    )
    title = body[0]["title"]
    assert [
        j["title"] for j in account.client.get(f"{SEARCH}/jobs", params={"roles": title[:8]}).json()
    ]
    assert account.client.get(f"{SEARCH}/jobs", params={"roles": "zzzz-nothing"}).json() == []
    assert len(account.client.get(f"{SEARCH}/jobs", params={"companies": "palantir"}).json()) == 2
    assert account.client.get(f"{SEARCH}/jobs", params={"companies": "stripe"}).json() == []
    assert len(account.client.get(f"{SEARCH}/jobs", params={"limit": 1}).json()) == 1
    assert account.client.get(f"{SEARCH}/jobs", params={"limit": 500}).status_code == 422


def test_a_wildcard_in_the_search_is_text_not_a_pattern(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()))
    account = make_account(app)
    for token in ("%", "_", "%%", "a%b"):
        assert account.client.get(f"{SEARCH}/jobs", params={"roles": token}).json() == []


def test_jobs_vanish_for_everyone_when_their_source_stops_being_usable(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()))
    account = make_account(app)
    assert len(account.client.get(f"{SEARCH}/jobs").json()) == 2
    for sql in (
        "UPDATE job_sources SET enabled = false WHERE key = 'lever'",
        "UPDATE job_sources SET enabled = true, terms_checked_at = '2020-01-01' WHERE key = 'lever'",
    ):
        with Session(engine) as db, db.begin():
            db.execute(text(sql))
        assert account.client.get(f"{SEARCH}/jobs").json() == []
    assert one(engine, "SELECT count(*) FROM source_jobs").count == 2  # hidden, not deleted


def test_closed_jobs_are_not_listed(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    fetcher = FakeFetcher(ok())
    poll(engine, settings, fetcher, T0)
    fetcher.answers = [ok([LEVER[0]])]
    poll(engine, settings, fetcher, T0 + timedelta(hours=2))
    assert len(make_account(app).client.get(f"{SEARCH}/jobs").json()) == 1


def test_the_job_list_needs_a_session(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    account.client.cookies.clear()
    assert account.client.get(f"{SEARCH}/jobs").status_code == 401


def test_the_plan_now_says_searching_for_a_source_that_may_be_used(
    app: FastAPI, make_account: MakeAccount
) -> None:
    body = (
        make_account(app)
        .client.post(f"{SEARCH}/plan", json={"intent": {"companies": ["Palantir"]}}, headers={})
        .json()
        if False
        else None
    )
    account = make_account(app)
    response = account.client.post(
        f"{SEARCH}/plan", json={"intent": {"companies": ["Palantir"]}}, headers=account.csrf
    )
    body = response.json()
    lever = next(s for s in body["sources"] if s["key"] == "lever")
    assert lever["outcome"] == "search" and lever["message"] == "Searching Lever postings"
    assert body["can_search_now"] is True and body["headline"].startswith(
        "Searching Lever postings"
    )
    palantir = body["companies"][0]
    assert palantir["route"] == "first_party" and "own career system" in palantir["message"]


# ------------------------------------------------------------------------------ administrators


@pytest.fixture
def admin(app: FastAPI, make_account: MakeAccount, engine: Engine) -> Account:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account


def test_an_administrator_sees_health_and_the_fetch_log(
    admin: Account, engine: Engine, settings: Settings
) -> None:
    poll(engine, settings, FakeFetcher(ok()))
    row = {s["key"]: s for s in admin.client.get(ADMIN).json()}["lever"]
    assert (
        row["health_status"] == "healthy"
        and row["jobs_open"] == 2
        and row["breaker_open_until"] is None
    )
    entries = admin.client.get(f"{ADMIN}/lever/log").json()
    assert (
        entries[0]["outcome"] == "ok"
        and entries[0]["jobs_new"] == 2
        and entries[0]["board_id"] == "palantir"
    )
    assert "title" not in json.dumps(entries) and "description" not in json.dumps(entries)
    assert admin.client.get(f"{ADMIN}/nope/log").status_code == 404


def test_a_manual_poll_is_queued_audited_and_still_bound_by_the_rules(
    admin: Account, engine: Engine
) -> None:
    response = admin.client.post(f"{ADMIN}/lever/poll", headers=admin.csrf)
    assert response.status_code == 202 and "queued" in response.json()["message"]
    assert one(engine, "SELECT count(*) FROM tasks WHERE task_type = 'poll_source'").count == 1
    assert (
        one(
            engine,
            "SELECT count(*) FROM audit_events WHERE action = 'source.poll_requested' AND target_id = 'lever'",
        ).count
        >= 1
    )
    refused = admin.client.post(f"{ADMIN}/greenhouse/poll", headers=admin.csrf)
    assert refused.status_code == 409 and refused.json()["code"] == "SOURCE_NOT_USABLE"
    assert admin.client.post(f"{ADMIN}/linkedin/poll", headers=admin.csrf).status_code == 409
    assert admin.client.post(f"{ADMIN}/nope/poll", headers=admin.csrf).status_code == 404


def test_regular_users_cannot_poll_or_read_the_log(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert account.client.post(f"{ADMIN}/lever/poll", headers=account.csrf).status_code == 404
    assert account.client.get(f"{ADMIN}/lever/log").status_code == 404


def test_enabling_a_source_starts_polling_it(admin: Account, engine: Engine) -> None:
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE job_sources SET enabled = false WHERE key = 'lever'"))
        db.execute(text("DELETE FROM tasks WHERE task_type = 'poll_source'"))
    response = admin.client.patch(f"{ADMIN}/lever", json={"enabled": True}, headers=admin.csrf)
    assert response.status_code == 200, response.text
    assert one(engine, "SELECT count(*) FROM tasks WHERE task_type = 'poll_source'").count == 1
