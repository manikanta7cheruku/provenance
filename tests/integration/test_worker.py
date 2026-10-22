"""The worker loop against a real PostgreSQL, including the required crash-recovery scenario."""

import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_mail import MailDeliveryError
from pv_persistence import queue, workers
from pv_persistence.runs import create_run
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import Handler, TaskContext, TaskFailure
from pv_worker.handlers.send_email import handle_send_email
from pv_worker.runner import Worker


class CapturingMailer:
    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.error = error

    def send(self, to: str, subject: str, body: str) -> None:
        if self.error:
            raise self.error
        self.sent.append((to, subject, body))


def _worker(
    engine: Engine,
    settings: Settings,
    registry: dict[str, Handler],
    mailer: CapturingMailer | None = None,
) -> Worker:
    return Worker(
        engine,
        settings,
        registry,
        mailer=mailer or CapturingMailer(),
        worker_id=f"test-{uuid.uuid4().hex[:6]}",
    )


def _enqueue(engine: Engine, task_type: str, **kwargs: object) -> uuid.UUID:
    with Session(engine) as db, db.begin():
        task_id = queue.enqueue(
            db,
            task_type=task_type,
            idempotency_key=f"{task_type}:{uuid.uuid4().hex}",
            **kwargs,  # type: ignore[arg-type]
        )
    assert task_id is not None
    return task_id


def _task(engine: Engine, task_id: uuid.UUID) -> dict[str, object]:
    with Session(engine) as db:
        return dict(
            db.execute(
                text("SELECT state, attempts, payload, last_error FROM tasks WHERE id = :id"),
                {"id": task_id},
            )
            .mappings()
            .one()
        )


def _expire(engine: Engine, task_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text("UPDATE tasks SET locked_until = now() - interval '1 second' WHERE id = :id"),
            {"id": task_id},
        )


def test_an_idle_worker_reports_no_work(engine: Engine, settings: Settings) -> None:
    worker = _worker(engine, settings, {f"test.{uuid.uuid4().hex[:8]}": lambda ctx: None})
    assert worker.run_once() is False


def test_a_worker_only_claims_registered_types(engine: Engine, settings: Settings) -> None:
    mine, other = f"test.{uuid.uuid4().hex[:8]}", f"test.{uuid.uuid4().hex[:8]}"
    other_id = _enqueue(engine, other)
    _enqueue(engine, mine)
    worker = _worker(engine, settings, {mine: lambda ctx: None})
    assert worker.run_once() is True
    assert worker.run_once() is False
    assert _task(engine, other_id)["state"] == "queued"


def test_killed_worker_then_restart_runs_the_effect_exactly_once(
    engine: Engine, settings: Settings
) -> None:
    """Required scenario: start a task, kill the worker, restart, it completes exactly once."""
    task_type = f"test.{uuid.uuid4().hex[:8]}"
    effects: list[int] = []

    def handler(ctx: TaskContext) -> None:
        effects.append(ctx.attempt)

    task_id = _enqueue(engine, task_type)
    # First worker claims the task and is killed before doing anything: no completion is reported.
    dead = queue.claim_next(
        engine, worker_id="killed-worker", lease_seconds=60, task_types=[task_type]
    )
    assert dead is not None
    assert effects == []

    # A restarted worker cannot take it while the lease is valid...
    restarted = _worker(engine, settings, {task_type: handler})
    assert restarted.run_once() is False
    # ...but once the visibility timeout passes it does, exactly once.
    _expire(engine, task_id)
    assert restarted.run_once() is True
    assert restarted.run_once() is False
    assert effects == [2]
    row = _task(engine, task_id)
    assert row["state"] == "succeeded"
    assert row["attempts"] == 2


def test_handler_exceptions_retry_and_never_store_pii(engine: Engine, settings: Settings) -> None:
    task_type = f"test.{uuid.uuid4().hex[:8]}"

    def handler(ctx: TaskContext) -> None:
        raise ValueError("cannot reach ada@example.com using token " + "Q" * 40)

    task_id = _enqueue(engine, task_type, max_attempts=3)
    assert _worker(engine, settings, {task_type: handler}).run_once() is True
    row = _task(engine, task_id)
    assert row["state"] == "retry_scheduled"
    error = str(row["last_error"])
    assert "ValueError" in error
    assert "@" not in error
    assert "Q" * 40 not in error
    assert len(error) <= 300


def test_task_failure_can_be_permanent(engine: Engine, settings: Settings) -> None:
    task_type = f"test.{uuid.uuid4().hex[:8]}"

    def handler(ctx: TaskContext) -> None:
        raise TaskFailure("invalid input", retryable=False)

    task_id = _enqueue(engine, task_type, max_attempts=5)
    _worker(engine, settings, {task_type: handler}).run_once()
    assert _task(engine, task_id)["state"] == "dead_letter"


def test_dead_lettering_a_task_fails_its_run(
    engine: Engine, settings: Settings, app: FastAPI, make_account: Callable[..., Account]
) -> None:
    account = make_account(app)
    user_id = uuid.UUID(account.user_id)
    with tenant_session(engine, user_id) as db:
        run = create_run(db, owner_user_id=user_id, workflow_type="demo")
        run_id = run.id
    task_type = f"test.{uuid.uuid4().hex[:8]}"

    def handler(ctx: TaskContext) -> None:
        raise TaskFailure("nope", retryable=False)

    _enqueue(engine, task_type, owner_user_id=user_id, run_id=run_id)
    _worker(engine, settings, {task_type: handler}).run_once()
    response = account.client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["run"]["ui_state"] == "permanently_failed"


def test_verification_email_goes_from_queue_to_mailer_and_payload_is_erased(
    engine: Engine, settings: Settings, app: FastAPI, make_account: Callable[..., Account]
) -> None:
    account = make_account(app)  # registering queues a verification email
    mailer = CapturingMailer()
    worker = _worker(engine, settings, {"send_email": handle_send_email}, mailer)
    while worker.run_once():
        pass
    mine = [m for m in mailer.sent if m[0] == account.email]
    assert len(mine) == 1
    assert "/verify-email?token=" in mine[0][2]
    with Session(engine) as db:
        row = db.execute(
            text(
                "SELECT state, payload FROM tasks WHERE owner_user_id = :u AND task_type = 'send_email'"
            ),
            {"u": uuid.UUID(account.user_id)},
        ).one()
    assert row[0] == "succeeded"
    assert row[1] == {}


@pytest.mark.parametrize(
    ("retryable", "state"), [(True, "retry_scheduled"), (False, "dead_letter")]
)
def test_mail_errors_follow_their_retry_class_and_leave_no_address(
    engine: Engine,
    settings: Settings,
    app: FastAPI,
    make_account: Callable[..., Account],
    retryable: bool,
    state: str,
) -> None:
    account = make_account(app)
    mailer = CapturingMailer(MailDeliveryError("SMTP error 451", retryable=retryable))
    worker = _worker(engine, settings, {"send_email": handle_send_email}, mailer)
    while worker.run_once():
        pass
    with Session(engine) as db:
        row = db.execute(
            text(
                "SELECT state, last_error, payload FROM tasks WHERE owner_user_id = :u AND task_type = 'send_email'"
            ),
            {"u": uuid.UUID(account.user_id)},
        ).one()
    assert row[0] == state
    assert account.email not in str(row[1])
    if state == "dead_letter":
        assert "secret" not in row[2]  # the link token was erased
    # tidy: leave nothing retryable behind for a real worker
    with Session(engine) as db, db.begin():
        db.execute(
            text("DELETE FROM tasks WHERE owner_user_id = :u"), {"u": uuid.UUID(account.user_id)}
        )


def test_heartbeat_appears_and_is_removed_on_clean_stop(engine: Engine, settings: Settings) -> None:
    worker = _worker(engine, settings, {})
    worker.heartbeat()
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM worker_heartbeats WHERE worker_id = :w"),
                {"w": worker.worker_id},
            ).scalar_one()
            == 1
        )
    workers.forget(engine, worker.worker_id)
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM worker_heartbeats WHERE worker_id = :w"),
                {"w": worker.worker_id},
            ).scalar_one()
            == 0
        )
