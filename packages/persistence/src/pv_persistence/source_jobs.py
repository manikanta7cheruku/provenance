"""Jobs fetched from sources, the record of asking for them, and the health of each source.

Shared reference data, so these functions take a plain session. The rules of when to ask and when
to stop come from pv_domain.fetching. This module only keeps the numbers.

What is shown to people is decided on read (search_jobs): a job appears only while its source is
enabled, verified and in date. Switching a source off, or letting its review expire, hides its jobs
at once without deleting them.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from pv_domain.fetching import after_failure, health_for
from pv_domain.job_feed import FeedJob
from pv_domain.tasks import TASK_POLL_SOURCE
from pv_persistence.models import FetchLog, JobSource, SourceJob, SourceTarget
from pv_persistence.queue import enqueue

LOG_KEEP_DAYS = 30
MAX_PAGE = 50


@dataclass(frozen=True)
class StoreCounts:
    seen: int
    new: int
    changed: int
    closed: int


def get_targets(db: Session, source_key: str) -> dict[str, SourceTarget]:
    return {
        t.board_id: t
        for t in db.execute(
            select(SourceTarget).where(SourceTarget.source_key == source_key)
        ).scalars()
    }


def mark_target(
    db: Session,
    source_key: str,
    board_id: str,
    outcome: str,
    now: datetime,
    *,
    jobs_open: int | None = None,
) -> None:
    target = db.get(SourceTarget, (source_key, board_id))
    if target is None:
        target = SourceTarget(
            source_key=source_key, board_id=board_id, consecutive_errors=0, jobs_open=0
        )
        db.add(target)
    target.last_polled_at = now
    target.last_outcome = outcome
    target.consecutive_errors = 0 if outcome == "ok" else target.consecutive_errors + 1
    if jobs_open is not None:
        target.jobs_open = jobs_open


def store_listing(
    db: Session,
    source_key: str,
    board_id: str,
    jobs: tuple[FeedJob, ...],
    now: datetime,
    *,
    complete: bool,
) -> StoreCounts:
    """Save one board's jobs. A job already known is touched, or updated if its content changed.
    When the listing is complete, jobs it no longer holds are closed (never deleted)."""
    existing = {
        j.external_id: j
        for j in db.execute(
            select(SourceJob).where(
                SourceJob.source_key == source_key, SourceJob.board_id == board_id
            )
        ).scalars()
    }
    new = changed = 0
    seen_ids: set[str] = set()
    for job in jobs:
        seen_ids.add(job.external_id)
        row = existing.get(job.external_id)
        fields: dict[str, Any] = {
            "url": job.url,
            "title": job.title,
            "company_name": job.company_name,
            "location": job.location,
            "workplace": job.workplace,
            "employment_type": job.employment_type,
            "department": job.department,
            "description": job.description,
            "posted_at": job.posted_at,
            "source_updated_at": job.updated_at,
            "content_hash": job.content_hash,
        }
        if row is None:
            db.add(
                SourceJob(
                    source_key=source_key,
                    board_id=board_id,
                    external_id=job.external_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    **fields,
                )
            )
            new += 1
            continue
        if row.content_hash != job.content_hash:
            for name, value in fields.items():
                setattr(row, name, value)
            changed += 1
        row.last_seen_at = now
        row.closed_at = None
    closed = 0
    if complete:
        for external_id, row in existing.items():
            if external_id not in seen_ids and row.closed_at is None:
                row.closed_at = now
                closed += 1
    db.flush()
    return StoreCounts(len(jobs), new, changed, closed)


def count_open(db: Session, source_key: str, board_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(SourceJob)
            .where(
                SourceJob.source_key == source_key,
                SourceJob.board_id == board_id,
                SourceJob.closed_at.is_(None),
            )
        ).scalar_one()
    )


def log_fetch(
    db: Session,
    source_key: str,
    board_id: str | None,
    outcome: str,
    *,
    started_at: datetime,
    duration_ms: int = 0,
    http_status: int | None = None,
    bytes_read: int = 0,
    counts: StoreCounts | None = None,
    skipped: int = 0,
    error_class: str | None = None,
) -> None:
    db.add(
        FetchLog(
            source_key=source_key,
            board_id=board_id,
            started_at=started_at,
            duration_ms=duration_ms,
            outcome=outcome,
            http_status=http_status,
            bytes_read=bytes_read,
            jobs_seen=counts.seen if counts else 0,
            jobs_new=counts.new if counts else 0,
            jobs_changed=counts.changed if counts else 0,
            jobs_closed=counts.closed if counts else 0,
            jobs_skipped=skipped,
            error_class=error_class,
        )
    )


def recent_log(db: Session, source_key: str, limit: int = 20) -> list[FetchLog]:
    return list(
        db.execute(
            select(FetchLog)
            .where(FetchLog.source_key == source_key)
            .order_by(FetchLog.started_at.desc(), FetchLog.id.desc())
            .limit(limit)
        ).scalars()
    )


def prune_log(db: Session, now: datetime) -> int:
    result = db.execute(
        delete(FetchLog).where(FetchLog.started_at < now - timedelta(days=LOG_KEEP_DAYS))
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def record_success(db: Session, source_key: str, now: datetime) -> None:
    row = db.get(JobSource, source_key, with_for_update=True)
    if row is None:
        return
    row.failure_streak = 0
    row.breaker_open_until = None
    row.last_success_at = now
    row.health_status = health_for(0, None, now, ever_succeeded=True)


def record_failure(
    db: Session, source_key: str, now: datetime, *, wait: timedelta | None = None
) -> datetime | None:
    """Count a failure against the source. Returns when the breaker stays open until, if it does.
    `wait` is a longer pause the source asked for (Retry-After), which is never shortened."""
    row = db.get(JobSource, source_key, with_for_update=True)
    if row is None:
        return None
    streak, until = after_failure(row.failure_streak, now)
    if wait is not None and (until is None or now + wait > until):
        until = now + wait
    row.failure_streak = streak
    row.last_failure_at = now
    row.breaker_open_until = until
    row.health_status = health_for(
        streak, until, now, ever_succeeded=row.last_success_at is not None
    )
    return until


def search_jobs(
    db: Session,
    *,
    today: date,
    window_days: int,
    roles: list[str],
    companies: list[str],
    locations: list[str],
    work_mode: str | None,
    sources: list[str],
    limit: int,
    offset: int,
) -> list[tuple[SourceJob, JobSource]]:
    """Open jobs from sources that may be used right now. Filters are SQL, never the model."""
    oldest = today - timedelta(days=window_days)
    stmt = (
        select(SourceJob, JobSource)
        .join(JobSource, JobSource.key == SourceJob.source_key)
        .where(
            SourceJob.closed_at.is_(None),
            JobSource.enabled.is_(True),
            JobSource.compliance_status == "verified",
            JobSource.terms_checked_at.is_not(None),
            JobSource.terms_checked_at >= oldest,
        )
    )

    def like(column: Any, words: list[str]) -> Any:
        escaped = [w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for w in words]
        return or_(*[column.ilike(f"%{w}%", escape="\\") for w in escaped])

    if roles:
        stmt = stmt.where(or_(like(SourceJob.title, roles), like(SourceJob.department, roles)))
    if companies:
        stmt = stmt.where(
            or_(like(SourceJob.company_name, companies), SourceJob.board_id.in_(companies))
        )
    if locations:
        stmt = stmt.where(like(SourceJob.location, locations))
    if work_mode and work_mode != "any":
        stmt = stmt.where(SourceJob.workplace == work_mode)
    if sources:
        stmt = stmt.where(SourceJob.source_key.in_(sources))
    stmt = (
        stmt.order_by(
            func.coalesce(SourceJob.posted_at, SourceJob.first_seen_at).desc(), SourceJob.id
        )
        .limit(min(limit, MAX_PAGE))
        .offset(max(offset, 0))
    )
    return [(job, src) for job, src in db.execute(stmt).all()]


def source_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(SourceJob.source_key, func.count())
        .where(SourceJob.closed_at.is_(None))
        .group_by(SourceJob.source_key)
    ).all()
    return {key: int(n) for key, n in rows}


def utcnow() -> datetime:
    return datetime.now(UTC)


def queue_poll(
    db: Session,
    source_key: str,
    *,
    now: datetime,
    delay: timedelta = timedelta(0),
    interval_seconds: int = 3600,
    chain: bool = True,
) -> bool:
    """Queue a poll. Returns False when one is already queued for the same slot.

    The key names a slot as long as the poll interval, so two chains that land in the same slot
    become one and a source never ends up polled twice as often. A poll with chain=False runs once
    and does not schedule another."""
    due = now + delay
    slot = int(due.timestamp() // max(interval_seconds, 60))
    kind = "chain" if chain else "once"
    task = enqueue(
        db,
        task_type=TASK_POLL_SOURCE,
        idempotency_key=f"{TASK_POLL_SOURCE}:{source_key}:{kind}:{slot}",
        payload={"args": {"source_key": source_key, "chain": chain}},
        delay_seconds=max(delay.total_seconds(), 0.0),
        max_attempts=3,
    )
    return task is not None
