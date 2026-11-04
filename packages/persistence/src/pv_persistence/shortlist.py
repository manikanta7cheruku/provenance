"""The shortlist email: the schedule, the runs, and which jobs were already sent.

Call everything here inside tenant_session (Row Level Security applies). The schedule rules are in
pv_domain.shortlist. This module stores them and queues the next send. The task schedules its own next
run, so the email continues for as long as the person keeps it on.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_domain.shortlist import Candidate, Schedule, next_run, reason_for, select_shortlist
from pv_domain.tasks import TASK_SEND_SHORTLIST
from pv_persistence.models import ShortlistItem, ShortlistRun, ShortlistSettings
from pv_persistence.queue import enqueue
from pv_persistence.workrows import load_rows


def get_settings(db: Session, owner_id: uuid.UUID) -> ShortlistSettings | None:
    return db.execute(
        select(ShortlistSettings).where(ShortlistSettings.owner_user_id == owner_id)
    ).scalar_one_or_none()


def schedule_of(row: ShortlistSettings) -> Schedule:
    return Schedule(
        frequency=row.frequency,
        weekday=row.weekday,
        hour=row.hour,
        timezone=row.timezone,
        max_items=row.max_items,
    )


def cancel_waiting(db: Session, owner_id: uuid.UUID) -> None:
    """Nothing waiting to send for this person is left behind when the schedule changes."""
    db.execute(
        text(
            "UPDATE tasks SET state = 'cancelled', finished_at = now(), updated_at = now() "
            "WHERE task_type = :t AND owner_user_id = :o "
            "AND state IN ('queued', 'retry_scheduled')"
        ),
        {"t": TASK_SEND_SHORTLIST, "o": owner_id},
    )


def arm(db: Session, owner_id: uuid.UUID, slot: datetime, now: datetime, version: str = "") -> None:
    """Queue the send for a due time. The key holds the time, so a task that retries (and arranges the
    same next time again) makes one task. A person saving their settings passes a version, so that
    saving the same schedule twice still leaves one live task instead of finding the cancelled one."""
    delay = max(0.0, (slot - now).total_seconds())
    suffix = f":{version}" if version else ""
    enqueue(
        db,
        task_type=TASK_SEND_SHORTLIST,
        idempotency_key=f"{TASK_SEND_SHORTLIST}:{owner_id}:{slot.astimezone(UTC).isoformat()}{suffix}",
        payload={"args": {"slot": slot.astimezone(UTC).isoformat(), "manual": False}},
        owner_user_id=owner_id,
        max_attempts=4,
        delay_seconds=delay,
    )


def save_settings(
    db: Session, owner_id: uuid.UUID, schedule: Schedule, *, enabled: bool, now: datetime
) -> ShortlistSettings:
    """Store the schedule. Turning it on (or changing it while on) works out the next time and queues
    it. Turning it off cancels what is waiting."""
    row = get_settings(db, owner_id)
    if row is None:
        row = ShortlistSettings(owner_user_id=owner_id)
    row.enabled = enabled
    row.frequency = schedule.frequency
    row.weekday = schedule.weekday
    row.hour = schedule.hour
    row.timezone = schedule.timezone
    row.max_items = schedule.max_items
    row.updated_at = now
    # The next time is set together with "on", so no write ever sees one without the other.
    row.next_run_at = next_run(now, schedule) if enabled else None
    db.add(row)
    db.flush()
    cancel_waiting(db, owner_id)
    if row.next_run_at is not None:
        arm(db, owner_id, row.next_run_at, now, version=now.isoformat())
    return row


def sent_posting_ids(db: Session, owner_id: uuid.UUID) -> set[str]:
    """Every job that was in an earlier email. They are never sent again."""
    rows = db.execute(
        select(ShortlistItem.posting_id).where(ShortlistItem.owner_user_id == owner_id)
    ).scalars()
    return {str(p) for p in rows}


def get_run(db: Session, owner_id: uuid.UUID, slot: datetime) -> ShortlistRun | None:
    return db.execute(
        select(ShortlistRun).where(
            ShortlistRun.owner_user_id == owner_id, ShortlistRun.slot == slot
        )
    ).scalar_one_or_none()


def record_run(
    db: Session,
    *,
    owner_id: uuid.UUID,
    slot: datetime,
    outcome: str,
    posting_ids: list[uuid.UUID],
    manual: bool,
    error_code: str | None = None,
) -> ShortlistRun | None:
    """Write what happened for a due time. Returns None when that time already has a run, so a retried
    task cannot record (or send) it twice."""
    run = ShortlistRun(
        owner_user_id=owner_id,
        slot=slot,
        manual=manual,
        outcome=outcome,
        item_count=len(posting_ids),
        error_code=error_code,
    )
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError:
        return None
    for position, posting_id in enumerate(posting_ids, start=1):
        db.add(
            ShortlistItem(
                run_id=run.id, posting_id=posting_id, owner_user_id=owner_id, position=position
            )
        )
    db.flush()
    return run


def recent_runs(db: Session, owner_id: uuid.UUID, limit: int = 5) -> list[ShortlistRun]:
    return list(
        db.execute(
            select(ShortlistRun)
            .where(ShortlistRun.owner_user_id == owner_id)
            .order_by(ShortlistRun.created_at.desc(), ShortlistRun.id)
            .limit(limit)
        ).scalars()
    )


MAX_JOBS_CONSIDERED = 500


def compute_shortlist(db: Session, owner_id: uuid.UUID, limit: int) -> list[tuple[Candidate, str]]:
    """The jobs that would go in an email now, best first, each with its reason. The email and the
    preview on the settings page both come from here, so they always agree."""
    postings, rows, reasons = load_rows(db, owner_id, MAX_JOBS_CONSIDERED)
    by_id = {str(p.id): p for p in postings}
    candidates = [
        Candidate(
            id=r.id,
            title=r.title,
            company=r.company,
            location=r.location,
            work_mode=r.work_mode,
            eligibility=r.eligibility,
            band=r.band,
            state=r.state,
            created_at=r.created_at,
        )
        for r in rows
        if r.id in by_id
    ]
    chosen = select_shortlist(candidates, already_sent=sent_posting_ids(db, owner_id), limit=limit)
    return [(c, reason_for(c, reasons.get(uuid.UUID(c.id), ""))) for c in chosen]
