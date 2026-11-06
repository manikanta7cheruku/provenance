"""The admin console's answers: is it healthy, is work stuck, what does it cost, what happened to a run.

Each number answers one operational question and comes from a system table (tasks, workers, model
calls, sources, the audit log, rate limit counters). No tenant table is read here, so nothing a
person wrote can reach this screen (ADR-0023). Alerts are decided by pv_domain.alerts from one
snapshot of those numbers, so the screen, the check command and the tests all agree.
"""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api import __version__
from pv_api.metrics import RequestStatsSnapshot
from pv_api.schemas import (
    AlertOut,
    ComponentOut,
    HealthOut,
    RateLimitOut,
    RequestStatsOut,
    SecurityEventOut,
    SourceHealthOut,
    ThresholdsOut,
    TraceCallOut,
    TraceOut,
    TraceTaskOut,
    TroubleTaskOut,
    UsageOut,
    UsageRowOut,
)
from pv_config import Settings
from pv_domain.alerts import Alert, Snapshot, Thresholds, evaluate, worst
from pv_persistence.models import JobSource
from pv_persistence.observability import (
    queue_numbers,
    rate_limit_pressure,
    security_counts,
    trace_run,
    trouble_tasks,
    usage_report,
)
from pv_persistence.snapshot import build_snapshot as snapshot_of

USAGE_DAYS = (7, 30)

_SECURITY_LABELS = {
    "auth.login_failed": "Failed sign-ins",
    "auth.password_change_failed": "Failed password changes",
    "origin_rejected": "Requests blocked for their origin",
    "csrf_rejected": "Requests without a valid CSRF token",
}


def thresholds_for(settings: Settings) -> Thresholds:
    return Thresholds(daily_spend_ceiling_usd=settings.llm_daily_spend_ceiling_usd)


def build_snapshot(
    engine: Engine, stats: RequestStatsSnapshot | None, now: datetime | None = None
) -> Snapshot:
    return snapshot_of(
        engine,
        requests=None if stats is None else stats.requests,
        server_errors=None if stats is None else stats.server_errors,
        p95_ms=None if stats is None else stats.p95_ms,
        now=now,
    )


def alert_out(alert: Alert) -> AlertOut:
    return AlertOut(**asdict(alert))


def _queue_component(snapshot: Snapshot, limits: Thresholds) -> ComponentOut:
    age = snapshot.oldest_waiting_seconds
    if snapshot.queue_waiting == 0:
        return ComponentOut(name="Queue", status="ok", detail="Nothing is waiting.")
    detail = f"{snapshot.queue_waiting} waiting, the oldest for {_span(age or 0)}."
    if age is not None and age >= limits.queue_stale_critical_seconds:
        return ComponentOut(name="Queue", status="critical", detail=detail)
    if age is not None and age >= limits.queue_stale_warning_seconds:
        return ComponentOut(name="Queue", status="warning", detail=detail)
    return ComponentOut(name="Queue", status="ok", detail=detail)


def _span(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    return f"{round(seconds / 3600, 1)} hours"


def _components(
    snapshot: Snapshot, limits: Thresholds, stats: RequestStatsSnapshot | None
) -> list[ComponentOut]:
    workers = ComponentOut(
        name="Workers",
        status="ok"
        if snapshot.workers_alive
        else ("critical" if snapshot.queue_waiting else "warning"),
        detail=(
            f"{snapshot.workers_alive} running"
            + (
                f", {snapshot.workers_stale} not heard from lately"
                if snapshot.workers_stale
                else ""
            )
            + "."
        ),
    )
    enabled = [s for s in snapshot.sources if s.enabled]
    unhealthy = [
        s for s in enabled if s.breaker_open or s.failure_streak >= limits.source_failure_streak
    ]
    if not enabled:
        sources = ComponentOut(
            name="Job sources", status="unknown", detail="No source is switched on."
        )
    else:
        sources = ComponentOut(
            name="Job sources",
            status="warning" if unhealthy else "ok",
            detail=f"{len(enabled) - len(unhealthy)} of {len(enabled)} switched-on sources are healthy.",
        )
    if snapshot.llm_calls_24h == 0:
        model = ComponentOut(
            name="Model provider", status="unknown", detail="No model calls in the last day."
        )
    else:
        rate = snapshot.llm_errors_24h / snapshot.llm_calls_24h
        bad = snapshot.llm_calls_24h >= limits.llm_min_calls and rate >= limits.llm_error_rate
        model = ComponentOut(
            name="Model provider",
            status="warning" if bad else "ok",
            detail=f"{snapshot.llm_errors_24h} of {snapshot.llm_calls_24h} calls failed in the last day.",
        )
    if stats is None or stats.requests == 0:
        api = ComponentOut(
            name="API", status="ok", detail=f"Version {__version__}. No requests measured yet."
        )
    else:
        api = ComponentOut(
            name="API",
            status="ok",
            detail=f"Version {__version__}. {stats.requests} requests in the last {stats.window_seconds // 60} minutes.",
        )
    database = ComponentOut(
        name="Database",
        status="ok" if snapshot.database_ok else "critical",
        detail="Answering." if snapshot.database_ok else "Not answering.",
    )
    migrations = ComponentOut(
        name="Migrations",
        status={"ok": "ok", "behind": "critical"}.get(snapshot.migrations, "unknown"),  # type: ignore[arg-type]
        detail={
            "ok": "The database matches the code.",
            "behind": "The database is behind the code.",
        }.get(snapshot.migrations, "Could not be checked."),
    )
    if not snapshot.evaluation_seen:
        evaluation = ComponentOut(
            name="Evaluation",
            status="unknown",
            detail="No evaluation has been stored yet. Run python -m pv_eval run --store.",
        )
    elif snapshot.evaluation_failed:
        evaluation = ComponentOut(
            name="Evaluation",
            status="warning",
            detail="Not passing: " + ", ".join(snapshot.evaluation_failed) + ".",
        )
    else:
        evaluation = ComponentOut(
            name="Evaluation", status="ok", detail="The latest run of every suite passed."
        )
    return [
        api,
        database,
        migrations,
        workers,
        _queue_component(snapshot, limits),
        sources,
        model,
        evaluation,
    ]


def health(
    engine: Engine,
    settings: Settings,
    stats: RequestStatsSnapshot | None,
    now: datetime | None = None,
) -> HealthOut:
    moment = now or datetime.now(UTC)
    limits = thresholds_for(settings)
    snapshot = build_snapshot(engine, stats, moment)
    alerts = evaluate(snapshot, limits)
    with Session(engine) as db:
        trouble = trouble_tasks(db)
        security = security_counts(db, moment - timedelta(hours=24))
        pressure = rate_limit_pressure(db, moment - timedelta(hours=24))
        rows = {s.key: s for s in db.query(JobSource).all()}
    status = worst(alerts)
    headline = {
        "ok": "Everything measured looks healthy.",
        "warning": f"{len(alerts)} {'thing needs' if len(alerts) == 1 else 'things need'} a look.",
        "critical": f"{sum(1 for a in alerts if a.severity == 'critical')} critical, {len(alerts)} in all.",
    }[status]
    measured = stats is not None and stats.requests > 0
    return HealthOut(
        status=status,  # type: ignore[arg-type]
        headline=headline,
        version=__version__,
        environment=settings.environment,
        generated_at=moment,
        components=_components(snapshot, limits, stats),
        alerts=[alert_out(a) for a in alerts],
        requests=RequestStatsOut(
            measured=measured,
            window_minutes=(stats.window_seconds // 60) if stats else 15,
            requests=stats.requests if stats else 0,
            server_errors=stats.server_errors if stats else 0,
            client_errors=stats.client_errors if stats else 0,
            p50_ms=stats.p50_ms if stats else None,
            p95_ms=stats.p95_ms if stats else None,
        ),
        queue_by_state=queue_numbers_state(engine, moment),
        oldest_waiting_seconds=snapshot.oldest_waiting_seconds,
        trouble_tasks=[
            TroubleTaskOut(
                id=t.id,
                task_type=t.task_type,
                state=t.state,  # type: ignore[arg-type]
                attempts=t.attempts,
                max_attempts=t.max_attempts,
                run_id=t.run_id,
                last_error=t.last_error,
                run_after=t.run_after,
            )
            for t in trouble
        ],
        sources=[
            SourceHealthOut(
                key=s.key,
                name=s.name,
                enabled=s.enabled,
                status=rows[s.key].health_status if s.key in rows else "unknown",
                breaker_open=s.breaker_open,
                failure_streak=s.failure_streak,
                last_success_at=rows[s.key].last_success_at if s.key in rows else None,
                last_failure_at=rows[s.key].last_failure_at if s.key in rows else None,
            )
            for s in snapshot.sources
        ],
        security_24h=[
            SecurityEventOut(action=a, label=_SECURITY_LABELS.get(a, a), count=c)
            for a, c in security.items()
        ],
        rate_limits_24h=[RateLimitOut(policy=p, counters_over=n) for p, n in pressure.items()],
        thresholds=ThresholdsOut(
            queue_stale_warning_seconds=limits.queue_stale_warning_seconds,
            queue_stale_critical_seconds=limits.queue_stale_critical_seconds,
            source_failure_streak=limits.source_failure_streak,
            llm_error_rate=limits.llm_error_rate,
            daily_spend_ceiling_usd=limits.daily_spend_ceiling_usd,
            server_error_rate=limits.server_error_rate,
            p95_ms=limits.p95_ms,
            auth_failures_per_hour=limits.auth_failures_per_hour,
        ),
    )


def queue_numbers_state(engine: Engine, moment: datetime) -> dict[str, int]:
    with Session(engine) as db:
        return queue_numbers(db, moment).by_state


def usage(engine: Engine, settings: Settings, days: int) -> UsageOut:
    with Session(engine) as db:
        report = usage_report(db, days)

    def rows(items: list) -> list[UsageRowOut]:  # type: ignore[type-arg]
        return [UsageRowOut(**asdict(r)) for r in items]

    return UsageOut(
        days=days,
        calls=report.totals.calls,
        errors=report.totals.errors,
        input_tokens=report.input_tokens,
        output_tokens=report.output_tokens,
        cost_usd=report.totals.cost_usd,
        accounts=report.accounts,
        average_latency_ms=report.average_latency_ms,
        highest_account_share=report.highest_account_share,
        daily_spend_ceiling_usd=settings.llm_daily_spend_ceiling_usd,
        by_model=rows(report.by_model),
        by_purpose=rows(report.by_purpose),
        by_day=rows(report.by_day),
        by_plan=rows(report.by_plan),
    )


def trace(engine: Engine, run_id: uuid.UUID) -> TraceOut:
    with Session(engine) as db:
        tasks, calls = trace_run(db, run_id)
    return TraceOut(
        run_id=run_id,
        found=bool(tasks or calls),
        tasks=[TraceTaskOut(**asdict(t)) for t in tasks],
        calls=[TraceCallOut(**asdict(c)) for c in calls],
    )
