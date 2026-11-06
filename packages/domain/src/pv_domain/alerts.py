"""Alerts: which things an operator should look at now, and what to do about each.

Pure rules over a snapshot of measurements, so every rule is testable and the same snapshot always
gives the same alerts. Each alert says what is wrong in a sentence, what to do first, and where its
runbook section is (an alert without a runbook is incomplete). Thresholds are starting points: they
are named in one place, shown on the screen as such, and are meant to be set from measurement once
there is real traffic (carryover).

A measurement that was not taken (for example request timings when the check runs from the command
line) is None, and no rule fires on a missing measurement. Missing is never read as healthy or as
broken: the screen says "not measured".
"""

from dataclasses import dataclass, field

CRITICAL = "critical"
WARNING = "warning"
_ORDER = {CRITICAL: 0, WARNING: 1}

RUNBOOK = "operations/runbooks/alerts.md"


@dataclass(frozen=True)
class SourceHealth:
    key: str
    name: str
    enabled: bool
    breaker_open: bool
    failure_streak: int


@dataclass(frozen=True)
class Snapshot:
    database_ok: bool = True
    migrations: str = "ok"  # ok, behind or unknown
    workers_alive: int = 1
    workers_stale: int = 0
    queue_waiting: int = 0
    oldest_waiting_seconds: int | None = None
    stuck_tasks: int = 0
    dead_letters_24h: int = 0
    dead_letters_total: int = 0
    sources: tuple[SourceHealth, ...] = ()
    llm_calls_24h: int = 0
    llm_errors_24h: int = 0
    llm_cost_24h_usd: float = 0.0
    requests: int | None = None
    server_errors: int | None = None
    p95_ms: int | None = None
    auth_failures_1h: int = 0
    origin_rejections_1h: int = 0


@dataclass(frozen=True)
class Thresholds:
    """Starting points chosen before there was traffic to measure."""

    queue_stale_warning_seconds: int = 300
    queue_stale_critical_seconds: int = 1800
    source_failure_streak: int = 3
    llm_error_rate: float = 0.25
    llm_min_calls: int = 10
    daily_spend_ceiling_usd: float = 0.0  # 0 means no ceiling is set
    spend_warning_fraction: float = 0.8
    server_error_rate: float = 0.05
    min_requests: int = 50
    p95_ms: int = 3000
    auth_failures_per_hour: int = 50
    origin_rejections_per_hour: int = 20


@dataclass(frozen=True)
class Alert:
    key: str
    severity: str
    title: str
    detail: str
    action: str
    runbook: str = field(default=RUNBOOK)


def _minutes(seconds: int) -> str:
    return f"{max(1, round(seconds / 60))} minutes"


def evaluate(snapshot: Snapshot, limits: Thresholds | None = None) -> tuple[Alert, ...]:
    t = limits or Thresholds()
    s = snapshot
    found: list[Alert] = []

    if not s.database_ok:
        found.append(
            Alert(
                "database_down",
                CRITICAL,
                "The database is not answering",
                "Nothing can be read or saved until it is back.",
                "Check the database container or service, then its disk space.",
            )
        )
    if s.migrations == "behind":
        found.append(
            Alert(
                "migrations_behind",
                CRITICAL,
                "The database is behind the code",
                "The running version expects tables or columns that are not there yet.",
                "Run the migration step, then restart the API and the worker.",
            )
        )

    if s.workers_alive == 0:
        waiting = s.queue_waiting > 0
        found.append(
            Alert(
                "no_worker",
                CRITICAL if waiting else WARNING,
                "No worker is running",
                (
                    f"{s.queue_waiting} tasks are waiting and nothing will run them."
                    if waiting
                    else "Nothing is waiting yet, but anything started now will not run."
                ),
                "Start the worker and check its log for why it stopped.",
            )
        )

    if s.oldest_waiting_seconds is not None and s.workers_alive > 0:
        age = s.oldest_waiting_seconds
        if age >= t.queue_stale_critical_seconds:
            level = CRITICAL
        elif age >= t.queue_stale_warning_seconds:
            level = WARNING
        else:
            level = ""
        if level:
            found.append(
                Alert(
                    "queue_stale",
                    level,
                    "Work has been waiting a long time",
                    f"The oldest waiting task is {_minutes(age)} old and {s.queue_waiting} are waiting.",
                    "Look at what the workers are doing and whether one task is holding them up.",
                )
            )

    if s.stuck_tasks > 0:
        found.append(
            Alert(
                "stuck_tasks",
                WARNING,
                "Some tasks have outlived their lease",
                f"{s.stuck_tasks} running tasks have not renewed their lease.",
                "A worker may have died mid task. The next claim retries them. Check the worker log.",
            )
        )

    if s.dead_letters_24h > 0:
        found.append(
            Alert(
                "dead_letters",
                WARNING,
                "Tasks gave up",
                f"{s.dead_letters_24h} tasks were dead-lettered in the last day ({s.dead_letters_total} in all).",
                "Open the dead letters, read the reason, fix the cause, then requeue what can be.",
            )
        )

    for source in s.sources:
        if not source.enabled:
            continue
        if source.breaker_open:
            found.append(
                Alert(
                    f"source_breaker_{source.key}",
                    WARNING,
                    f"{source.name} is paused after failures",
                    f"The circuit breaker is open after {source.failure_streak} failures in a row.",
                    "Read the source's fetch log. It retries by itself when the pause ends.",
                )
            )
        elif source.failure_streak >= t.source_failure_streak:
            found.append(
                Alert(
                    f"source_failing_{source.key}",
                    WARNING,
                    f"{source.name} keeps failing",
                    f"The last {source.failure_streak} fetches failed.",
                    "Read the source's fetch log and check its page for a change.",
                )
            )

    if (
        s.llm_calls_24h >= t.llm_min_calls
        and s.llm_errors_24h / s.llm_calls_24h >= t.llm_error_rate
    ):
        found.append(
            Alert(
                "llm_errors",
                WARNING,
                "Many model calls are failing",
                f"{s.llm_errors_24h} of {s.llm_calls_24h} model calls failed in the last day.",
                "Check the provider's status and the key, then the error classes in the model usage table.",
            )
        )

    ceiling = t.daily_spend_ceiling_usd
    if ceiling > 0:
        if s.llm_cost_24h_usd >= ceiling:
            found.append(
                Alert(
                    "spend_over_ceiling",
                    CRITICAL,
                    "Daily model spend is over the ceiling",
                    f"${s.llm_cost_24h_usd:.2f} in the last day against a ceiling of ${ceiling:.2f}.",
                    "Find the heaviest operation in cost and usage, and lower its plan limits or pause it.",
                )
            )
        elif s.llm_cost_24h_usd >= ceiling * t.spend_warning_fraction:
            found.append(
                Alert(
                    "spend_near_ceiling",
                    WARNING,
                    "Daily model spend is nearing the ceiling",
                    f"${s.llm_cost_24h_usd:.2f} in the last day against a ceiling of ${ceiling:.2f}.",
                    "Look at cost and usage before it passes the ceiling.",
                )
            )

    if s.requests is not None and s.server_errors is not None and s.requests >= t.min_requests:
        rate = s.server_errors / s.requests
        if rate >= t.server_error_rate:
            found.append(
                Alert(
                    "api_errors",
                    CRITICAL,
                    "The API is returning server errors",
                    f"{s.server_errors} of {s.requests} recent requests failed on our side ({rate:.0%}).",
                    "Read the API log for unhandled_exception lines and quote a request id.",
                )
            )
    if (
        s.p95_ms is not None
        and s.requests is not None
        and s.requests >= t.min_requests
        and s.p95_ms >= t.p95_ms
    ):
        found.append(
            Alert(
                "api_slow",
                WARNING,
                "The API is slow",
                f"The slowest 5 percent of recent requests took {s.p95_ms} ms or more.",
                "Check the database, the queue and the host load. Look for one slow route in the log.",
            )
        )

    if s.auth_failures_1h >= t.auth_failures_per_hour:
        found.append(
            Alert(
                "auth_failures",
                WARNING,
                "Many failed sign-ins",
                f"{s.auth_failures_1h} failed sign-ins or password checks in the last hour.",
                "Check whether it is one address or one account in the audit log. Rate limits are already applied.",
            )
        )
    if s.origin_rejections_1h >= t.origin_rejections_per_hour:
        found.append(
            Alert(
                "origin_rejections",
                WARNING,
                "Many requests from the wrong origin",
                f"{s.origin_rejections_1h} requests were blocked for their origin in the last hour.",
                "Check ALLOWED_ORIGINS is right for this deployment, then the audit log for a pattern.",
            )
        )

    return tuple(sorted(found, key=lambda a: (_ORDER[a.severity], a.key)))


def worst(alerts: tuple[Alert, ...]) -> str:
    """ "ok", "warning" or "critical": the one word the page headline is built from."""
    if any(a.severity == CRITICAL for a in alerts):
        return CRITICAL
    return WARNING if alerts else "ok"
