"""Worker heartbeats. The admin overview reads these to show which workers are alive."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def heartbeat(engine: Engine, *, worker_id: str, hostname: str, tasks_processed: int) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                """
                INSERT INTO worker_heartbeats (worker_id, hostname, tasks_processed)
                VALUES (:worker, :host, :processed)
                ON CONFLICT (worker_id) DO UPDATE
                   SET last_seen_at = now(), tasks_processed = EXCLUDED.tasks_processed
                """
            ),
            {"worker": worker_id, "host": hostname, "processed": tasks_processed},
        )


def forget(engine: Engine, worker_id: str) -> None:
    """Called on clean shutdown so a stopped worker does not linger as 'stale'."""
    with Session(engine) as db, db.begin():
        db.execute(
            text("DELETE FROM worker_heartbeats WHERE worker_id = :worker"),
            {"worker": worker_id},
        )
