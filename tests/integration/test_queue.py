"""The task queue against a real PostgreSQL. These tests are the proof of the guarantees in ADR-0022."""

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.redaction import MAX_ERROR_LENGTH
from pv_persistence import queue


@pytest.fixture
def task_type() -> str:
    # A unique type per test: the claim filter then ignores every other test's tasks, and a
    # real worker (which only claims registered types) would ignore these too.
    return f"test.{uuid.uuid4().hex[:10]}"


@pytest.fixture
def add_task(engine: Engine, task_type: str) -> Callable[..., uuid.UUID]:
    def _add(**kwargs: object) -> uuid.UUID:
        with Session(engine) as db, db.begin():
            task_id = queue.enqueue(
                db,
                task_type=task_type,
                idempotency_key=f"{task_type}:{uuid.uuid4().hex}",
                **kwargs,  # type: ignore[arg-type]
            )
        assert task_id is not None
        return task_id

    return _add


def _row(engine: Engine, task_id: uuid.UUID) -> dict[str, object]:
    with Session(engine) as db:
        row = (
            db.execute(
                text(
                    "SELECT state, attempts, payload, last_error, locked_by, finished_at "
                    "FROM tasks WHERE id = :id"
                ),
                {"id": task_id},
            )
            .mappings()
            .one()
        )
    return dict(row)


def _expire_lease(engine: Engine, task_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text("UPDATE tasks SET locked_until = now() - interval '1 second' WHERE id = :id"),
            {"id": task_id},
        )


def _claim(
    engine: Engine, task_type: str, worker: str = "w1", lease: float = 60
) -> queue.ClaimedTask | None:
    return queue.claim_next(engine, worker_id=worker, lease_seconds=lease, task_types=[task_type])


def test_enqueue_with_the_same_key_creates_one_task(engine: Engine, task_type: str) -> None:
    key = f"{task_type}:same"
    with Session(engine) as db, db.begin():
        first = queue.enqueue(db, task_type=task_type, idempotency_key=key)
        second = queue.enqueue(db, task_type=task_type, idempotency_key=key)
    assert first is not None
    assert second is None
    with Session(engine) as db:
        count = db.execute(
            text("SELECT count(*) FROM tasks WHERE idempotency_key = :k"), {"k": key}
        ).scalar_one()
    assert count == 1


def test_enqueue_rolls_back_with_the_caller_transaction(engine: Engine, task_type: str) -> None:
    key = f"{task_type}:rollback"
    with pytest.raises(RuntimeError), Session(engine) as db, db.begin():
        queue.enqueue(db, task_type=task_type, idempotency_key=key)
        raise RuntimeError("the surrounding change failed")
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM tasks WHERE idempotency_key = :k"), {"k": key}
            ).scalar_one()
            == 0
        )


def test_delayed_task_is_not_claimable_yet(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    add_task(delay_seconds=3600)
    assert _claim(engine, task_type) is None


def test_many_workers_racing_for_one_task_give_it_to_exactly_one(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task()
    barrier = threading.Barrier(8)

    def race(n: int) -> queue.ClaimedTask | None:
        barrier.wait()
        return _claim(engine, task_type, worker=f"w{n}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(race, range(8)))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert winners[0].id == task_id
    assert winners[0].attempts == 1


def test_many_workers_share_many_tasks_without_overlap(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    expected = {add_task() for _ in range(24)}
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()

    def drain(n: int) -> None:
        while (task := _claim(engine, task_type, worker=f"w{n}")) is not None:
            with lock:
                claimed.append(task.id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(drain, range(4)))
    assert len(claimed) == len(set(claimed)) == 24
    assert set(claimed) == expected


def test_success_erases_the_whole_payload(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task(payload={"args": {"a": 1}, "secret": {"token": "s3cret"}})
    task = _claim(engine, task_type)
    assert task is not None and task.payload["secret"] == {"token": "s3cret"}
    assert queue.complete(engine, task.id, "w1") is True
    row = _row(engine, task_id)
    assert row["state"] == "succeeded"
    assert row["payload"] == {}
    assert row["finished_at"] is not None


def test_retryable_failure_schedules_a_retry_then_dead_letters_and_erases_the_secret(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task(max_attempts=2, payload={"args": {"keep": "me"}, "secret": {"to": "x"}})
    first = _claim(engine, task_type)
    assert first is not None and first.attempts == 1
    outcome = queue.fail(engine, first, "w1", retryable=True, error="temporary", delay_seconds=0)
    assert outcome == "retry_scheduled"
    assert _row(engine, task_id)["state"] == "retry_scheduled"

    second = _claim(engine, task_type)
    assert second is not None and second.attempts == 2
    outcome = queue.fail(
        engine, second, "w1", retryable=True, error="still failing", delay_seconds=0
    )
    assert outcome == "dead_letter"
    row = _row(engine, task_id)
    assert row["state"] == "dead_letter"
    assert row["last_error"] == "still failing"
    assert row["payload"] == {"args": {"keep": "me"}}  # references stay, the secret is gone


def test_retry_waits_for_the_backoff_delay(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    add_task()
    task = _claim(engine, task_type)
    assert task is not None
    queue.fail(engine, task, "w1", retryable=True, error="later", delay_seconds=3600)
    assert _claim(engine, task_type) is None


def test_permanent_failure_dead_letters_at_once(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task(max_attempts=5)
    task = _claim(engine, task_type)
    assert task is not None
    assert (
        queue.fail(engine, task, "w1", retryable=False, error="bad input", delay_seconds=0)
        == "dead_letter"
    )
    assert _row(engine, task_id)["state"] == "dead_letter"


def test_error_text_is_truncated_to_the_limit(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task()
    task = _claim(engine, task_type)
    assert task is not None
    queue.fail(engine, task, "w1", retryable=False, error="x" * 1000, delay_seconds=0)
    assert len(str(_row(engine, task_id)["last_error"])) == MAX_ERROR_LENGTH


def test_a_crashed_worker_task_is_recovered_and_completes_exactly_once(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    """The required test: start a task, kill the worker, restart, it completes exactly once."""
    task_id = add_task()

    crashed = _claim(engine, task_type, worker="worker-a")  # claimed, then the process dies
    assert crashed is not None
    assert _claim(engine, task_type, worker="worker-b") is None  # lease still valid: hidden

    _expire_lease(engine, task_id)  # time passes: the visibility timeout expires
    recovered = _claim(engine, task_type, worker="worker-b")
    assert recovered is not None and recovered.id == task_id
    assert recovered.attempts == 2

    assert queue.complete(engine, task_id, "worker-b") is True
    # worker-a wakes up late and tries to report: it no longer holds the lease.
    assert queue.complete(engine, task_id, "worker-a") is False
    assert (
        queue.fail(engine, crashed, "worker-a", retryable=True, error="late", delay_seconds=0)
        == "lease_lost"
    )

    row = _row(engine, task_id)
    assert row["state"] == "succeeded"
    assert row["attempts"] == 2
    assert _claim(engine, task_type, worker="worker-c") is None  # nothing is left to run twice


def test_a_task_that_keeps_killing_its_worker_is_dead_lettered(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task(max_attempts=2)
    for _ in range(2):
        assert _claim(engine, task_type) is not None
        _expire_lease(engine, task_id)
    assert _claim(engine, task_type) is None  # third claim exceeds max_attempts and dead-letters
    row = _row(engine, task_id)
    assert row["state"] == "dead_letter"
    assert "attempts exhausted" in str(row["last_error"])


def test_extend_lease_only_works_for_the_holder(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task()
    task = _claim(engine, task_type, worker="holder", lease=30)
    assert task is not None
    assert queue.extend_lease(engine, task_id, "holder", 60) is True
    assert queue.extend_lease(engine, task_id, "someone-else", 60) is False


def test_requeue_gives_a_dead_letter_a_fresh_start(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    task_id = add_task(max_attempts=1)
    task = _claim(engine, task_type)
    assert task is not None
    queue.fail(engine, task, "w1", retryable=True, error="boom", delay_seconds=0)
    assert _row(engine, task_id)["state"] == "dead_letter"
    with Session(engine) as db, db.begin():
        assert queue.requeue_dead_letter(db, task_id) is True
        assert queue.requeue_dead_letter(db, task_id) is False  # no longer dead
    row = _row(engine, task_id)
    assert (row["state"], row["attempts"], row["last_error"]) == ("queued", 0, None)


def test_purge_removes_old_finished_tasks_only(
    engine: Engine, task_type: str, add_task: Callable[..., uuid.UUID]
) -> None:
    old_done = add_task()
    recent_done = add_task()
    waiting = add_task()
    for task_id in (old_done, recent_done):
        with Session(engine) as db, db.begin():
            db.execute(
                text("UPDATE tasks SET state='succeeded', finished_at = :ts WHERE id = :id"),
                {"id": task_id, "ts": "2000-01-01" if task_id == old_done else "2999-01-01"},
            )
    queue.purge_finished(engine, older_than_days=7)
    with Session(engine) as db:
        left = {
            r[0]
            for r in db.execute(text("SELECT id FROM tasks WHERE task_type = :t"), {"t": task_type})
        }
    assert left == {recent_done, waiting}
