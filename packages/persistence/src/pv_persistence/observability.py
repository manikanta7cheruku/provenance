"""Operational measurements for the admin console and the alert check.

Everything here reads system tables only: tasks, worker heartbeats, model calls, job sources, the
audit log and rate limit counters. None of them holds a person's content, and none is protected by
Row Level Security, which has no admin exception (ADR-0023). Nothing here reads a tenant table, so
the console can show how the system is doing without ever being able to show what anyone wrote.

Call with a plain Session (no tenant set).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from pv_domain.alerts import SourceHealth
from pv_domain.ratelimit import DEFAULT_POLICIES
from pv_persistence.models import (
    AuditEvent,
    JobSource,
    LlmCall,
    Task,
    User,
    WorkerHeartbeat,
)

STALE_WORKER_SECONDS = 60
SECURITY_ACTIONS_SHOWN = 12


@dataclass(frozen=True)
class QueueNumbers:
    by_state: dict[str, int]
    waiting: int
    oldest_waiting_seconds: int | None
    stuck: int
    dead_letters_24h: int
    dead_letters_total: int
    workers_alive: int
    workers_stale: int


def queue_numbers(db: Session, now: datetime | None = None) -> QueueNumbers:
    moment = now or datetime.now(UTC)
    by_state = {
        state: count
        for state, count in db.execute(select(Task.state, func.count()).group_by(Task.state)).all()
    }
    oldest = db.execute(
        select(func.min(Task.run_after)).where(
            Task.state.in_(("queued", "retry_scheduled")), Task.run_after <= moment
        )
    ).scalar_one()
    stuck = db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.state == "running", Task.locked_until < moment)
    ).scalar_one()
    dead_24h = db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.state == "dead_letter", Task.finished_at >= moment - timedelta(hours=24))
    ).scalar_one()
    seen = db.execute(select(WorkerHeartbeat.last_seen_at)).scalars().all()
    alive = sum(1 for s in seen if (moment - s).total_seconds() < STALE_WORKER_SECONDS)
    return QueueNumbers(
        by_state=by_state,
        waiting=by_state.get("queued", 0) + by_state.get("retry_scheduled", 0),
        oldest_waiting_seconds=None
        if oldest is None
        else max(0, int((moment - oldest).total_seconds())),
        stuck=int(stuck),
        dead_letters_24h=int(dead_24h),
        dead_letters_total=by_state.get("dead_letter", 0),
        workers_alive=alive,
        workers_stale=len(seen) - alive,
    )


@dataclass(frozen=True)
class WaitingTask:
    id: uuid.UUID
    task_type: str
    state: str
    attempts: int
    max_attempts: int
    run_id: uuid.UUID | None
    last_error: str | None
    run_after: datetime


def trouble_tasks(db: Session, limit: int = 20) -> list[WaitingTask]:
    """Tasks that are being retried, or running past their lease: the ones to look at first."""
    now = datetime.now(UTC)
    rows = db.execute(
        select(Task)
        .where(
            (Task.state == "retry_scheduled")
            | ((Task.state == "running") & (Task.locked_until < now))
        )
        .order_by(Task.updated_at.desc())
        .limit(limit)
    ).scalars()
    return [
        WaitingTask(
            id=t.id,
            task_type=t.task_type,
            state="stuck" if t.state == "running" else "retrying",
            attempts=t.attempts,
            max_attempts=t.max_attempts,
            run_id=t.run_id,
            last_error=t.last_error,
            run_after=t.run_after,
        )
        for t in rows
    ]


def source_health(db: Session) -> list[SourceHealth]:
    now = datetime.now(UTC)
    return [
        SourceHealth(
            key=s.key,
            name=s.display_name,
            enabled=s.enabled,
            breaker_open=s.breaker_open_until is not None and s.breaker_open_until > now,
            failure_streak=s.failure_streak,
        )
        for s in db.execute(select(JobSource).order_by(JobSource.key)).scalars()
    ]


@dataclass(frozen=True)
class ModelUse:
    calls: int
    errors: int
    cost_usd: float


def llm_totals(db: Session, since: datetime) -> ModelUse:
    calls, errors, cost = db.execute(
        select(
            func.count(),
            func.count().filter(LlmCall.status == "error"),
            func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0),
        ).where(LlmCall.created_at >= since)
    ).one()
    return ModelUse(int(calls), int(errors), float(cost))


def security_counts(db: Session, since: datetime) -> dict[str, int]:
    return {
        action: int(count)
        for action, count in db.execute(
            select(AuditEvent.action, func.count())
            .where(AuditEvent.category == "security", AuditEvent.created_at >= since)
            .group_by(AuditEvent.action)
            .order_by(func.count().desc())
            .limit(SECURITY_ACTIONS_SHOWN)
        ).all()
    }


def rate_limit_pressure(db: Session, since: datetime) -> dict[str, int]:
    """For each policy, how many counters went over its limit since `since`. No one is named."""
    rows = db.execute(
        text(
            "SELECT split_part(bucket_key, ':', 1) AS policy, hits "
            "FROM rate_limit_buckets WHERE window_start >= :since"
        ),
        {"since": since},
    ).all()
    over: dict[str, int] = {}
    for raw_policy, raw_hits in rows:
        policy, hits = str(raw_policy), int(str(raw_hits))
        known = DEFAULT_POLICIES.get(policy)
        if known is not None and hits > known.limit:
            over[policy] = over.get(policy, 0) + 1
    return dict(sorted(over.items(), key=lambda kv: -kv[1]))


# ---- cost and usage


@dataclass(frozen=True)
class UsageRow:
    key: str
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


def _usage(db: Session, since: datetime, *group: Any) -> list[tuple[Any, ...]]:
    return list(
        db.execute(
            select(
                *group,
                func.count(),
                func.count().filter(LlmCall.status == "error"),
                func.coalesce(func.sum(LlmCall.input_tokens), 0),
                func.coalesce(func.sum(LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0),
            )
            .where(LlmCall.created_at >= since)
            .group_by(*group)
            .order_by(func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0).desc())
        ).all()
    )


def _rows(raw: list[tuple[Any, ...]], width: int) -> list[UsageRow]:
    return [
        UsageRow(
            key=" / ".join(str(v) for v in r[:width]),
            calls=int(r[width]),
            errors=int(r[width + 1]),
            input_tokens=int(r[width + 2]),
            output_tokens=int(r[width + 3]),
            cost_usd=float(r[width + 4]),
        )
        for r in raw
    ]


@dataclass(frozen=True)
class UsageReport:
    totals: ModelUse
    input_tokens: int
    output_tokens: int
    accounts: int
    by_model: list[UsageRow]
    by_purpose: list[UsageRow]
    by_day: list[UsageRow]
    by_plan: list[UsageRow]
    average_latency_ms: int | None
    highest_account_share: float | None


def usage_report(db: Session, days: int, now: datetime | None = None) -> UsageReport:
    moment = now or datetime.now(UTC)
    since = (moment - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    totals = llm_totals(db, since)
    aggregate: Any = db.execute(
        select(
            func.coalesce(func.sum(LlmCall.input_tokens), 0),
            func.coalesce(func.sum(LlmCall.output_tokens), 0),
            func.avg(LlmCall.latency_ms),
            func.count(func.distinct(LlmCall.user_id)),
        ).where(LlmCall.created_at >= since)
    ).one()
    in_tok, out_tok, latency, accounts = aggregate
    day = func.date_trunc("day", LlmCall.created_at)
    by_day_raw = _usage(db, since, day)
    by_day = sorted(
        (
            UsageRow(
                key=r[0].date().isoformat(),
                calls=int(r[1]),
                errors=int(r[2]),
                input_tokens=int(r[3]),
                output_tokens=int(r[4]),
                cost_usd=float(r[5]),
            )
            for r in by_day_raw
        ),
        key=lambda row: row.key,
    )
    per_account = (
        db.execute(
            select(func.sum(LlmCall.estimated_cost_usd))
            .where(LlmCall.created_at >= since, LlmCall.user_id.is_not(None))
            .group_by(LlmCall.user_id)
        )
        .scalars()
        .all()
    )
    spend = [float(v or 0) for v in per_account]
    share = (max(spend) / sum(spend)) if spend and sum(spend) > 0 else None
    return UsageReport(
        totals=totals,
        input_tokens=int(in_tok),
        output_tokens=int(out_tok),
        accounts=int(accounts),
        by_model=_rows(_usage(db, since, LlmCall.provider, LlmCall.model), 2),
        by_purpose=_rows(_usage(db, since, LlmCall.purpose), 1),
        by_day=by_day,
        by_plan=_plan_rows(db, since),
        average_latency_ms=None if latency is None else round(float(latency)),
        highest_account_share=share,
    )


def _plan_rows(db: Session, since: datetime) -> list[UsageRow]:
    """Cost by the plan the person was on when the call was made. NULL is the default plan."""
    plan = func.coalesce(LlmCall.plan_id, "default plan")
    return _rows(_usage(db, since, plan), 1)


@dataclass(frozen=True)
class FeedbackCounts:
    labels: int
    people: int


def feedback_counts(db: Session) -> FeedbackCounts:
    """How many "was this right?" labels exist and from how many people. Counters kept by triggers:
    no label and no person is read here."""
    labels = db.execute(
        text("SELECT labels FROM feedback_totals WHERE id = 1")
    ).scalar_one_or_none()
    people: object = db.execute(text("SELECT count(*) FROM feedback_people")).scalar_one()
    return FeedbackCounts(int(str(labels or 0)), int(str(people)))


@dataclass(frozen=True)
class DatabaseNumbers:
    connections: int
    max_connections: int
    size_bytes: int


def database_numbers(db: Session) -> DatabaseNumbers:
    """How busy and how big the database is. A connection count and a size, nothing else."""
    connections: object = db.execute(
        text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
    ).scalar_one()
    maximum: object = db.execute(
        text("SELECT setting::int FROM pg_settings WHERE name = 'max_connections'")
    ).scalar_one()
    size: object = db.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
    return DatabaseNumbers(int(str(connections)), int(str(maximum)), int(str(size)))


# ---- one run, from the system tables only


@dataclass(frozen=True)
class TraceTask:
    id: uuid.UUID
    task_type: str
    state: str
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None
    owner_email: str | None


@dataclass(frozen=True)
class TraceCall:
    purpose: str
    provider: str
    model: str
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    status: str
    error_class: str | None
    created_at: datetime


def trace_run(db: Session, run_id: uuid.UUID) -> tuple[list[TraceTask], list[TraceCall]]:
    tasks = db.execute(
        select(Task, User.email)
        .outerjoin(User, User.id == Task.owner_user_id)
        .where(Task.run_id == run_id)
        .order_by(Task.created_at)
    ).all()
    calls = db.execute(
        select(LlmCall).where(LlmCall.run_id == run_id).order_by(LlmCall.created_at)
    ).scalars()
    return (
        [
            TraceTask(
                id=t.id,
                task_type=t.task_type,
                state=t.state,
                attempts=t.attempts,
                max_attempts=t.max_attempts,
                last_error=t.last_error,
                created_at=t.created_at,
                finished_at=t.finished_at,
                owner_email=str(email) if email else None,
            )
            for t, email in tasks
        ],
        [
            TraceCall(
                purpose=c.purpose,
                provider=c.provider,
                model=c.model,
                prompt_version=c.prompt_version,
                input_tokens=c.input_tokens,
                output_tokens=c.output_tokens,
                cost_usd=float(c.estimated_cost_usd),
                latency_ms=c.latency_ms,
                status=c.status,
                error_class=c.error_class,
                created_at=c.created_at,
            )
            for c in calls
        ],
    )
