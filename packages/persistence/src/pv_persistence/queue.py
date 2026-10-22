"""PostgreSQL task queue (ADR-0002, refined by ADR-0022).

Delivery is AT LEAST ONCE: a task may run more than once, but it is never silently
lost. Handlers must therefore be idempotent.

How the guarantees are built:
  enqueue          INSERT ... ON CONFLICT DO NOTHING on a unique idempotency key.
  claim            one UPDATE ... FROM (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1).
                   Two workers never get the same row: the second skips locked rows.
  lease            a claimed task is 'running' with locked_until in the future. If the
                   worker dies, the lease expires and another worker claims the task
                   again (the visibility timeout). Each claim increments attempts.
  poison tasks     a task that keeps killing its worker reaches attempts > max_attempts
                   and is dead-lettered instead of being claimed forever.
  finishing        complete and fail only act while this worker still holds the lease
                   (locked_by matches), so a slow worker cannot overwrite a newer attempt.

This module never returns payloads to callers outside the worker and never logs them.
"""

import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.redaction import MAX_ERROR_LENGTH

logger = logging.getLogger("pv_persistence.queue")

FailOutcome = Literal["retry_scheduled", "dead_letter", "lease_lost"]


@dataclass(frozen=True)
class ClaimedTask:
    id: uuid.UUID
    task_type: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    owner_user_id: uuid.UUID | None
    run_id: uuid.UUID | None


def _rowcount(result: object) -> int:
    return int(cast("CursorResult[Any]", result).rowcount)


def enqueue(
    db: Session,
    *,
    task_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    owner_user_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    max_attempts: int = 5,
    delay_seconds: float = 0.0,
) -> uuid.UUID | None:
    """Add a task inside the caller's transaction. Returns None if the key already exists.

    Enqueueing in the same transaction as the change that needs the work means the two
    commit or roll back together: no "row saved but task lost" and no "task for a row
    that was never saved".
    """
    row = db.execute(
        text(
            """
            INSERT INTO tasks (task_type, payload, idempotency_key, owner_user_id, run_id,
                               max_attempts, run_after)
            VALUES (:task_type, CAST(:payload AS jsonb), :key, :owner, :run, :max_attempts,
                    now() + make_interval(secs => :delay))
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "task_type": task_type,
            "payload": json.dumps(payload or {}),
            "key": idempotency_key,
            "owner": owner_user_id,
            "run": run_id,
            "max_attempts": max_attempts,
            "delay": float(delay_seconds),
        },
    ).first()
    return None if row is None else cast("uuid.UUID", row[0])


_CLAIM_SQL = text(
    """
    WITH next AS (
        SELECT id FROM tasks
         WHERE task_type = ANY(:types)
           AND ((state IN ('queued', 'retry_scheduled') AND run_after <= now())
                OR (state = 'running' AND locked_until < now()))
         ORDER BY run_after
         LIMIT 1
         FOR UPDATE SKIP LOCKED
    )
    UPDATE tasks AS t
       SET state = 'running',
           attempts = t.attempts + 1,
           locked_by = :worker,
           locked_until = now() + make_interval(secs => :lease),
           updated_at = now()
      FROM next
     WHERE t.id = next.id
    RETURNING t.id, t.task_type, t.payload, t.attempts, t.max_attempts,
              t.owner_user_id, t.run_id
    """
)


def claim_next(
    engine: Engine,
    *,
    worker_id: str,
    lease_seconds: float,
    task_types: Sequence[str],
) -> ClaimedTask | None:
    """Claim one due task of the given types, or None. Exhausted tasks are dead-lettered."""
    while True:
        with Session(engine) as db, db.begin():
            row = (
                db.execute(
                    _CLAIM_SQL,
                    {"types": list(task_types), "worker": worker_id, "lease": float(lease_seconds)},
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        task = ClaimedTask(
            id=row["id"],
            task_type=row["task_type"],
            payload=dict(row["payload"] or {}),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            owner_user_id=row["owner_user_id"],
            run_id=row["run_id"],
        )
        if task.attempts > task.max_attempts:
            # The previous attempt used the last allowed try and its worker never reported back.
            logger.warning(
                "task_exhausted",
                extra={
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "attempts": task.attempts,
                },
            )
            _dead_letter(engine, task.id, "Worker lost: attempts exhausted without a result.", None)
            continue
        return task


def _dead_letter(engine: Engine, task_id: uuid.UUID, error: str, worker_id: str | None) -> bool:
    with Session(engine) as db, db.begin():
        result = db.execute(
            text(
                """
                UPDATE tasks
                   SET state = 'dead_letter', payload = payload - 'secret',
                       last_error = :error, locked_until = NULL, locked_by = NULL,
                       finished_at = now(), updated_at = now()
                 WHERE id = :id AND state = 'running'
                   AND (CAST(:worker AS text) IS NULL OR locked_by = :worker)
                """
            ),
            {"id": task_id, "error": error[:MAX_ERROR_LENGTH], "worker": worker_id},
        )
        return _rowcount(result) == 1


def complete(engine: Engine, task_id: uuid.UUID, worker_id: str) -> bool:
    """Mark success and erase the payload. False means this worker no longer held the lease."""
    with Session(engine) as db, db.begin():
        result = db.execute(
            text(
                """
                UPDATE tasks
                   SET state = 'succeeded', payload = '{}'::jsonb, last_error = NULL,
                       locked_until = NULL, locked_by = NULL,
                       finished_at = now(), updated_at = now()
                 WHERE id = :id AND state = 'running' AND locked_by = :worker
                """
            ),
            {"id": task_id, "worker": worker_id},
        )
        return _rowcount(result) == 1


def fail(
    engine: Engine,
    task: ClaimedTask,
    worker_id: str,
    *,
    retryable: bool,
    error: str,
    delay_seconds: float,
) -> FailOutcome:
    """Record a failed attempt: schedule a retry, or dead-letter when no retry is allowed."""
    error = error[:MAX_ERROR_LENGTH]
    if retryable and task.attempts < task.max_attempts:
        with Session(engine) as db, db.begin():
            result = db.execute(
                text(
                    """
                    UPDATE tasks
                       SET state = 'retry_scheduled', last_error = :error,
                           run_after = now() + make_interval(secs => :delay),
                           locked_until = NULL, locked_by = NULL, updated_at = now()
                     WHERE id = :id AND state = 'running' AND locked_by = :worker
                    """
                ),
                {"id": task.id, "error": error, "delay": float(delay_seconds), "worker": worker_id},
            )
        return "retry_scheduled" if _rowcount(result) == 1 else "lease_lost"
    return "dead_letter" if _dead_letter(engine, task.id, error, worker_id) else "lease_lost"


def extend_lease(engine: Engine, task_id: uuid.UUID, worker_id: str, lease_seconds: float) -> bool:
    """Long handlers call this so their lease does not expire while they are still working."""
    with Session(engine) as db, db.begin():
        result = db.execute(
            text(
                """
                UPDATE tasks
                   SET locked_until = now() + make_interval(secs => :lease), updated_at = now()
                 WHERE id = :id AND state = 'running' AND locked_by = :worker
                """
            ),
            {"id": task_id, "worker": worker_id, "lease": float(lease_seconds)},
        )
        return _rowcount(result) == 1


def requeue_dead_letter(db: Session, task_id: uuid.UUID) -> bool:
    """Operator action: give a dead-lettered task a fresh set of attempts."""
    result = db.execute(
        text(
            """
            UPDATE tasks
               SET state = 'queued', attempts = 0, run_after = now(), last_error = NULL,
                   finished_at = NULL, updated_at = now()
             WHERE id = :id AND state = 'dead_letter'
            """
        ),
        {"id": task_id},
    )
    return _rowcount(result) == 1


def purge_finished(engine: Engine, *, older_than_days: int) -> int:
    """Delete old finished tasks and stale worker rows. Dead letters are kept for inspection."""
    with Session(engine) as db, db.begin():
        tasks = db.execute(
            text(
                """
                DELETE FROM tasks
                 WHERE state IN ('succeeded', 'cancelled')
                   AND finished_at < now() - make_interval(days => :days)
                """
            ),
            {"days": older_than_days},
        )
        db.execute(
            text("DELETE FROM worker_heartbeats WHERE last_seen_at < now() - interval '1 day'")
        )
        return _rowcount(tasks)
