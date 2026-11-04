"""The shortlist email: when it is due, and which few jobs go in it.

Pure code. Nothing here asks a model anything. The same jobs and the same history always give the same
shortlist, so a person can see why a job is in it, and why another is not.

  - The schedule is the person's own: daily or weekly, an hour, and their time zone. The next time is
    worked out in their local clock, so "Monday 8" stays Monday 8 across a change of clocks.
  - A job is a candidate only when it is still open to a decision (new, saved or approved for
    preparation), its evidence check is complete, a hard requirement does not rule it out, and its fit
    is Strong or Good. A job already in an earlier email is never sent again.
  - Candidates are ranked by fit, then by how clear eligibility is, then saved jobs before new ones,
    then newest. Ties are broken by id so the order never changes between runs.
  - Every job in the email carries its reason, written from facts the product already computed.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FREQUENCIES = ("daily", "weekly")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MIN_ITEMS = 1
MAX_ITEMS = 10
DEFAULT_ITEMS = 5
DEFAULT_HOUR = 8
DEFAULT_TIMEZONE = "UTC"

OPEN_STATES = frozenset({"new", "saved", "approved_for_prep"})
SHORTLIST_BANDS = ("strong", "good")
_BAND_RANK = {"strong": 0, "good": 1}
_ELIGIBILITY_RANK = {"eligible": 0, "uncertain": 1, "requires_user_input": 2}

BAND_WORDS = {"strong": "Strong match", "good": "Good match"}
ELIGIBILITY_SENTENCES = {
    "eligible": "Nothing stands in your way.",
    "uncertain": "A few points are worth a closer look.",
    "requires_user_input": "It needs an answer from you before you can be sure.",
}

NOT_VERIFIED_MESSAGE = (
    "Verify your email address first. The shortlist is only sent to a verified address."
)


class ScheduleError(ValueError):
    """The schedule is not valid. fields maps a field name to a sentence for the person."""

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("; ".join(fields.values()))
        self.fields = fields


@dataclass(frozen=True)
class Schedule:
    frequency: str = "weekly"
    weekday: int = 0  # Monday is 0
    hour: int = DEFAULT_HOUR
    timezone: str = DEFAULT_TIMEZONE
    max_items: int = DEFAULT_ITEMS


def valid_timezone(name: str) -> bool:
    if not name or len(name) > 64 or name.startswith(("/", ".")) or ".." in name:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def _bounded(
    raw: dict[str, object], key: str, low: int, high: int, default: int | None
) -> int | None:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        return None
    return value


def clean_schedule(raw: dict[str, object]) -> Schedule:
    """A schedule from untrusted input, or ScheduleError naming what to fix."""
    problems: dict[str, str] = {}
    frequency = raw.get("frequency")
    if not isinstance(frequency, str) or frequency not in FREQUENCIES:
        problems["frequency"] = "Choose daily or weekly."
    weekday = _bounded(raw, "weekday", 0, 6, 0)
    if weekday is None:
        problems["weekday"] = "Choose a day of the week."
    hour = _bounded(raw, "hour", 0, 23, None)
    if hour is None:
        problems["hour"] = "Choose an hour from 0 to 23."
    zone = raw.get("timezone")
    if not isinstance(zone, str) or not valid_timezone(zone):
        problems["timezone"] = "Choose a time zone from the list."
    count = _bounded(raw, "max_items", MIN_ITEMS, MAX_ITEMS, DEFAULT_ITEMS)
    if count is None:
        problems["max_items"] = f"Choose between {MIN_ITEMS} and {MAX_ITEMS} jobs."
    if problems or not isinstance(frequency, str) or not isinstance(zone, str):
        raise ScheduleError(problems)
    return Schedule(
        frequency=frequency,
        weekday=weekday or 0,
        hour=hour or 0,
        timezone=zone,
        max_items=count or DEFAULT_ITEMS,
    )


def next_run(after: datetime, schedule: Schedule) -> datetime:
    """The first scheduled time strictly after `after`, as a UTC time.

    The day and hour are read on the person's own clock. A local time that does not exist (the hour
    skipped when clocks go forward) runs at the first moment after the gap, and one that happens
    twice (when clocks go back) runs the first time."""
    if after.tzinfo is None:
        raise ValueError("after must be a timezone-aware time")
    zone = ZoneInfo(schedule.timezone)
    local = after.astimezone(zone)
    day = local.date()
    if schedule.frequency == "weekly":
        day = day + timedelta(days=(schedule.weekday - local.weekday()) % 7)
    for _ in range(9):  # at most a week and a day ahead, so this always ends
        candidate = datetime.combine(day, time(schedule.hour), tzinfo=zone).astimezone(UTC)
        if candidate > after:
            return candidate
        day = day + timedelta(days=7 if schedule.frequency == "weekly" else 1)
    raise RuntimeError("no next run found")  # pragma: no cover


def describe_schedule(schedule: Schedule) -> str:
    when = f"{schedule.hour:02d}:00 ({schedule.timezone})"
    if schedule.frequency == "daily":
        return f"Every day at {when}"
    return f"Every {WEEKDAYS[schedule.weekday]} at {when}"


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    company: str
    location: str
    work_mode: str | None
    eligibility: str | None
    band: str | None
    state: str
    created_at: datetime


def is_candidate(c: Candidate) -> bool:
    return (
        c.state in OPEN_STATES and c.band in SHORTLIST_BANDS and c.eligibility in _ELIGIBILITY_RANK
    )


def select_shortlist(
    candidates: Iterable[Candidate], *, already_sent: set[str], limit: int
) -> list[Candidate]:
    """The few jobs worth a look, best first. Deterministic."""
    pool = [c for c in candidates if is_candidate(c) and c.id not in already_sent]

    def rank(c: Candidate) -> tuple[int, int, int, float, str]:
        return (
            _BAND_RANK[c.band or "good"],
            _ELIGIBILITY_RANK[c.eligibility or "uncertain"],
            0 if c.state in ("saved", "approved_for_prep") else 1,
            -c.created_at.timestamp(),
            c.id,
        )

    return sorted(pool, key=rank)[: max(MIN_ITEMS, min(limit, MAX_ITEMS))]


def reason_for(candidate: Candidate, supported_line: str) -> str:
    """The reason a job is in the email, from facts already computed. `supported_line` is the first
    sentence of the scoring reasons ("9 of 11 required requirements supported ...")."""
    band = BAND_WORDS.get(candidate.band or "", "Worth a look")
    eligibility = ELIGIBILITY_SENTENCES.get(candidate.eligibility or "", "")
    parts = [f"{band}: {supported_line.rstrip('.')}." if supported_line else f"{band}."]
    if eligibility:
        parts.append(eligibility)
    return " ".join(parts)
