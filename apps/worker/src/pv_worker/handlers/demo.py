"""A harmless task for operators: proves the queue, the worker and crash recovery work.

  python -m pv_worker.cli enqueue-demo --seconds 30

It sleeps (renewing its lease), then writes one audit event. The audit write is
idempotent: running the task twice still leaves exactly one event for the marker.
"""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from pv_persistence.models import AuditEvent
from pv_worker.contract import TaskContext, TaskFailure

MAX_SECONDS = 600


def handle_demo(ctx: TaskContext) -> None:
    seconds = ctx.args.get("seconds", 0)
    marker = ctx.args.get("marker")
    if not (isinstance(seconds, int) and isinstance(marker, str)):
        raise TaskFailure("Invalid demo task arguments.", retryable=False)
    if not 0 <= seconds <= MAX_SECONDS:
        raise TaskFailure("Invalid demo task arguments.", retryable=False)
    for _ in range(seconds):
        time.sleep(1)
        ctx.extend_lease()
    with Session(ctx.engine) as db, db.begin():
        already = db.execute(
            select(AuditEvent.id).where(
                AuditEvent.action == "system.demo_completed", AuditEvent.target_id == marker
            )
        ).first()
        if already is None:
            db.add(
                AuditEvent(
                    category="audit",
                    action="system.demo_completed",
                    target_type="task",
                    target_id=marker,
                    event_metadata={"seconds": seconds},
                )
            )
