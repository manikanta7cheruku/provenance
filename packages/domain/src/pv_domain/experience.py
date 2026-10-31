"""Years of experience, computed from the dates on a person's own work and internship entries.

The model never estimates this. Dates are YYYY or YYYY-MM or the word "present". Overlapping jobs
count once. Entries without a usable start date are ignored, and if nothing is usable the answer
is None ("unknown"), which is different from zero.
"""

import re
from collections.abc import Iterable
from datetime import date
from typing import Any

_DATE = re.compile(r"^(\d{4})(?:-(0[1-9]|1[0-2]))?$")
EXPERIENCE_TYPES = ("work", "internship")


def _month_index(value: Any, *, is_end: bool, today: date) -> int | None:
    """Months since year 0 for a date string. A bare year starts in January and ends in December."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text == "present":
        return today.year * 12 + (today.month - 1)
    match = _DATE.match(text)
    if not match:
        return None
    year, month = int(match.group(1)), match.group(2)
    return year * 12 + ((int(month) - 1) if month else (11 if is_end else 0))


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def years_of_experience(entries: Iterable[tuple[str, dict[str, Any]]], today: date) -> float | None:
    """Total years across work and internship entries, one decimal, or None without usable dates."""
    intervals: list[tuple[int, int]] = []
    for entry_type, data in entries:
        if entry_type not in EXPERIENCE_TYPES:
            continue
        start = _month_index(data.get("start_date"), is_end=False, today=today)
        if start is None:
            continue
        end = _month_index(data.get("end_date"), is_end=True, today=today)
        if end is None:
            end = start  # a start with no end counts as that one month, never as "still working"
        if end < start:
            continue
        intervals.append((start, end))
    if not intervals:
        return None
    months = sum(end - start + 1 for start, end in _merge(intervals))
    return round(months / 12, 1)
