"""The rules of polite fetching, as pure functions: when to ask, when to stop, how long to wait.

Three rules, enforced by the fetch layer whoever asks:
  1. A target is not asked again before the source's minimum poll interval has passed.
  2. A source that keeps failing is left alone (a circuit breaker), and only one careful probe is
     made when the wait is over. Other sources are not affected.
  3. A source that says "slow down" is obeyed: Retry-After is honoured, and failures back off.

Health words (healthy, degraded, down) come from the same counters, so what a person sees and what
the breaker does cannot disagree.
"""

from datetime import datetime, timedelta

FAILURES_TO_OPEN = 5
FAILURES_DEGRADED = 2
COOLDOWN_BASE = timedelta(minutes=15)
COOLDOWN_MAX = timedelta(hours=6)
RETRY_AFTER_MAX = timedelta(hours=1)
MIN_GAP_SECONDS = 1.0  # between two requests to the same host


def poll_due(last_polled_at: datetime | None, min_interval_seconds: int, now: datetime) -> bool:
    """Whether the minimum interval since the last poll of this target has passed."""
    if last_polled_at is None:
        return True
    return now - last_polled_at >= timedelta(seconds=min_interval_seconds)


def next_poll_at(
    last_polled_at: datetime | None, min_interval_seconds: int, now: datetime
) -> datetime:
    if last_polled_at is None:
        return now
    return max(now, last_polled_at + timedelta(seconds=min_interval_seconds))


def breaker_open(open_until: datetime | None, now: datetime) -> bool:
    """True while the source is being left alone."""
    return open_until is not None and now < open_until


def cooldown_for(failure_streak: int) -> timedelta:
    """How long to leave a source alone once it has failed enough times, doubling up to a limit."""
    if failure_streak < FAILURES_TO_OPEN:
        return timedelta(0)
    extra = min(failure_streak - FAILURES_TO_OPEN, 10)  # far past the limit, and no overflow
    wait: timedelta = COOLDOWN_BASE * (2**extra)
    return min(wait, COOLDOWN_MAX)


def after_failure(failure_streak: int, now: datetime) -> tuple[int, datetime | None]:
    """(new streak, the time the breaker stays open until, or None)."""
    streak = failure_streak + 1
    wait = cooldown_for(streak)
    return streak, (now + wait if wait else None)


def health_for(
    failure_streak: int, open_until: datetime | None, now: datetime, ever_succeeded: bool
) -> str:
    if breaker_open(open_until, now) or failure_streak >= FAILURES_TO_OPEN:
        return "down"
    if failure_streak >= FAILURES_DEGRADED:
        return "degraded"
    return "healthy" if ever_succeeded else "unknown"


def retry_after(header: str | None, now: datetime) -> timedelta | None:
    """Seconds from a Retry-After header, capped. HTTP dates are not trusted, only whole seconds."""
    if header is None:
        return None
    text = header.strip()
    if not text.isdigit():
        return None
    return min(timedelta(seconds=int(text)), RETRY_AFTER_MAX)
