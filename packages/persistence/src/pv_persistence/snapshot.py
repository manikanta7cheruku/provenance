"""One snapshot of how the system is doing, for the alert rules (pv_domain.alerts).

Shared by the admin console (the API) and by alert delivery (the worker), so both see the same
numbers and raise the same alerts. Reads system tables only, never a tenant table.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.alerts import Snapshot
from pv_persistence.evaluation import latest_per_suite
from pv_persistence.health import check_readiness
from pv_persistence.observability import (
    database_numbers,
    llm_totals,
    queue_numbers,
    security_counts,
    source_health,
)


def build_snapshot(
    engine: Engine,
    *,
    requests: int | None = None,
    server_errors: int | None = None,
    p95_ms: int | None = None,
    now: datetime | None = None,
) -> Snapshot:
    """Request numbers come from the API process, so they are None where they were not measured."""
    moment = now or datetime.now(UTC)
    report = check_readiness(engine)
    with Session(engine) as db:
        queue = queue_numbers(db, moment)
        sources = source_health(db)
        model = llm_totals(db, moment - timedelta(hours=24))
        security = security_counts(db, moment - timedelta(hours=1))
        latest = latest_per_suite(db)
        numbers = database_numbers(db)
    return Snapshot(
        database_ok=report.database,
        migrations=report.migrations,
        workers_alive=queue.workers_alive,
        workers_stale=queue.workers_stale,
        queue_waiting=queue.waiting,
        oldest_waiting_seconds=queue.oldest_waiting_seconds,
        stuck_tasks=queue.stuck,
        dead_letters_24h=queue.dead_letters_24h,
        dead_letters_total=queue.dead_letters_total,
        sources=tuple(sources),
        llm_calls_24h=model.calls,
        llm_errors_24h=model.errors,
        llm_cost_24h_usd=model.cost_usd,
        requests=requests,
        server_errors=server_errors,
        p95_ms=p95_ms,
        auth_failures_1h=security.get("auth.login_failed", 0)
        + security.get("auth.password_change_failed", 0),
        origin_rejections_1h=security.get("origin_rejected", 0),
        evaluation_failed=tuple(sorted(s for s, r in latest.items() if not r.passed)),
        evaluation_seen=bool(latest),
        connection_share=numbers.connections / numbers.max_connections
        if numbers.max_connections
        else None,
    )
