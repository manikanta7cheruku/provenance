"""Poll one job source: ask each of its boards politely, keep what comes back, and look after health.

The rules, none of which the caller can switch off:

  - a source is polled only while it may be used: enabled, verified, in date, with an adapter. If it
    stops being usable, the poll does nothing and does not schedule another
  - a board is not asked again before the source's minimum poll interval has passed, whoever asks
  - one request at a time, with a gap between requests to the same host
  - a source that keeps failing is left alone by a circuit breaker (pv_domain.fetching): while it is
    open nothing is requested, and when the wait ends one request is the probe. Other sources are
    never affected
  - 429 and Retry-After are obeyed. 404 for one board is that board's problem, not the source's
  - an answer that is not the kind expected is a failure and nothing is changed. Jobs a complete
    listing no longer holds are closed, never deleted, and never from an answer that was in doubt
  - every attempt and every skip is written to the fetch log, with counts and never job text

The task schedules its own next run, so polling continues for as long as the source is usable.
"""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.fetching import MIN_GAP_SECONDS, breaker_open, poll_due, retry_after
from pv_domain.job_feed import ADAPTERS, Adapter, FeedError, board_url
from pv_domain.sources import unavailable_reason
from pv_persistence.models import CompanyRow, JobSource
from pv_persistence.registry import to_record
from pv_persistence.source_jobs import (
    StoreCounts,
    count_open,
    get_targets,
    log_fetch,
    mark_target,
    prune_log,
    queue_poll,
    record_failure,
    record_success,
    store_listing,
)
from pv_worker.contract import TaskContext
from pv_worker.fetcher import Fetcher, FetchError, HttpxFetcher

Clock = Callable[[], datetime]


def handle_poll_source(ctx: TaskContext) -> None:
    fetcher = HttpxFetcher()
    try:
        run_poll(ctx, fetcher=fetcher)
    finally:
        fetcher.close()


def _now() -> datetime:
    return datetime.now(UTC)


def schedule_poll(
    engine: Engine, source_key: str, delay: timedelta, interval_seconds: int, now: datetime
) -> bool:
    with Session(engine) as db, db.begin():
        return queue_poll(
            db, source_key, now=now, delay=delay, interval_seconds=interval_seconds, chain=True
        )


def _boards(db: Session, adapter: Adapter) -> list[str]:
    rows = db.execute(
        select(CompanyRow.ats_board_id)
        .where(CompanyRow.ats_platform == adapter.key, CompanyRow.ats_board_id.is_not(None))
        .order_by(CompanyRow.ats_board_id)
    ).scalars()
    return [b for b in rows if b]


def run_poll(
    ctx: TaskContext,
    *,
    fetcher: Fetcher,
    sleep: Callable[[float], None] = time.sleep,
    clock: Clock = _now,
) -> None:
    source_key = str(ctx.args.get("source_key", ""))
    chain = ctx.args.get("chain") is True
    engine = ctx.engine
    window = ctx.settings.source_review_window_days
    now = clock()

    with Session(engine) as db, db.begin():
        row = db.get(JobSource, source_key)
        if row is None:
            return
        record = to_record(row)
        interval = record.min_poll_interval_seconds
        adapter = ADAPTERS.get(record.adapter or "")
        reason = unavailable_reason(record, now.date(), window)
        if reason is not None or adapter is None:
            log_fetch(
                db, source_key, None, "skipped_unusable", started_at=now, error_class="not_usable"
            )
            return  # not usable: do nothing and do not schedule another
        open_until = row.breaker_open_until
        if breaker_open(open_until, now):
            log_fetch(db, source_key, None, "skipped_breaker", started_at=now)
            wait = (open_until - now) if open_until else timedelta(0)
        else:
            wait = None
            boards = _boards(db, adapter)
            targets = get_targets(db, source_key)
            due = [
                b
                for b in boards
                if poll_due(targets[b].last_polled_at if b in targets else None, interval, now)
            ]
            for board in boards:
                if board not in due:
                    log_fetch(db, source_key, board, "skipped_interval", started_at=now)

    if wait is not None:
        if chain:
            schedule_poll(engine, source_key, wait, interval, now)
        return

    stop = False
    for index, board in enumerate(due):
        if stop:
            break
        ctx.extend_lease()
        if index:
            sleep(MIN_GAP_SECONDS)
        url = board_url(adapter, board)
        started = clock()
        if url is None:
            with Session(engine) as db, db.begin():
                log_fetch(
                    db,
                    source_key,
                    board,
                    "bad_response",
                    started_at=started,
                    error_class="bad_board_id",
                )
            continue
        stop = _poll_board(engine, fetcher, adapter, source_key, board, url, started, clock)

    after = clock()
    with Session(engine) as db, db.begin():
        prune_log(db, after)
        row = db.get(JobSource, source_key)
        until = row.breaker_open_until if row else None
    if chain:
        delay = max(
            timedelta(seconds=interval),
            (until - after) if until and until > after else timedelta(0),
        )
        schedule_poll(engine, source_key, delay, interval, after)


def _poll_board(
    engine: Engine,
    fetcher: Fetcher,
    adapter: Adapter,
    source_key: str,
    board: str,
    url: str,
    started: datetime,
    clock: Clock,
) -> bool:
    """Ask one board and record what happened. Returns True when polling this source should stop now."""
    t0 = time.perf_counter()

    def ms() -> int:
        return round((time.perf_counter() - t0) * 1000)

    try:
        response = fetcher.get(url, hosts=adapter.hosts)
    except FetchError as exc:
        with Session(engine) as db, db.begin():
            log_fetch(
                db,
                source_key,
                board,
                "network_error",
                started_at=started,
                duration_ms=ms(),
                error_class=exc.kind,
            )
            mark_target(db, source_key, board, "network_error", clock())
            record_failure(db, source_key, clock())
        return True
    status = response.status
    if status == 404:
        with Session(engine) as db, db.begin():
            log_fetch(
                db,
                source_key,
                board,
                "not_found",
                started_at=started,
                duration_ms=ms(),
                http_status=status,
            )
            mark_target(db, source_key, board, "not_found", clock())
        return False  # this board is gone or mistyped. The source is fine
    if status == 429 or status >= 500 or status in (401, 403):
        pause = retry_after(response.headers.get("retry-after"), clock())
        outcome = "rate_limited" if status == 429 else "http_error"
        with Session(engine) as db, db.begin():
            log_fetch(
                db,
                source_key,
                board,
                outcome,
                started_at=started,
                duration_ms=ms(),
                http_status=status,
            )
            mark_target(db, source_key, board, outcome, clock())
            record_failure(db, source_key, clock(), wait=pause)
        return True
    if status != 200:
        with Session(engine) as db, db.begin():
            log_fetch(
                db,
                source_key,
                board,
                "http_error",
                started_at=started,
                duration_ms=ms(),
                http_status=status,
            )
            mark_target(db, source_key, board, "http_error", clock())
        return False
    try:
        data: Any = json.loads(response.body)
        parsed = adapter.parse(data)
        if not parsed.jobs and parsed.skipped:
            raise FeedError("Every job in the answer was unusable.")
    except (ValueError, FeedError) as exc:  # json errors are ValueErrors
        with Session(engine) as db, db.begin():
            log_fetch(
                db, source_key, board, "bad_response", started_at=started, duration_ms=ms(),
                http_status=status, bytes_read=len(response.body), error_class=type(exc).__name__,
            )  # fmt: skip
            mark_target(db, source_key, board, "bad_response", clock())
            record_failure(db, source_key, clock())
        return True
    now = clock()
    with Session(engine) as db, db.begin():
        counts: StoreCounts = store_listing(
            db, source_key, board, parsed.jobs, now, complete=adapter.complete_listing
        )
        mark_target(db, source_key, board, "ok", now, jobs_open=count_open(db, source_key, board))
        record_success(db, source_key, now)
        log_fetch(
            db, source_key, board, "ok", started_at=started, duration_ms=ms(), http_status=status,
            bytes_read=len(response.body), counts=counts, skipped=parsed.skipped,
        )  # fmt: skip
    return False
