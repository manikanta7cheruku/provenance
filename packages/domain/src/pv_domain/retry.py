"""Retry policy for background tasks. Pure: no database, no clock, no framework.

Delay uses exponential backoff with "equal jitter": half of the ceiling is fixed and
half is random. The fixed half guarantees a real pause. The random half spreads out
workers that failed at the same moment, so they do not retry in lockstep (a
"thundering herd"). The random source is injectable so tests are deterministic.
"""

from collections.abc import Callable
from random import SystemRandom
from typing import Literal

BASE_DELAY_SECONDS = 5.0
MAX_DELAY_SECONDS = 300.0
_MAX_EXPONENT = 30  # keeps 2**n small enough that float math never overflows
_RANDOM = SystemRandom()

RetryDecision = Literal["retry", "dead_letter"]


def backoff_seconds(
    attempt: int,
    *,
    base: float = BASE_DELAY_SECONDS,
    cap: float = MAX_DELAY_SECONDS,
    rand: Callable[[], float] | None = None,
) -> float:
    """Seconds to wait before the next try. attempt is 1 for the first failure."""
    if attempt < 1:
        raise ValueError("attempt starts at 1")
    ceiling = min(cap, base * (2 ** min(attempt - 1, _MAX_EXPONENT)))
    draw = (rand or _RANDOM.random)()
    return float(ceiling / 2 + draw * ceiling / 2)


def decide_after_failure(attempts: int, max_attempts: int, *, retryable: bool) -> RetryDecision:
    """attempts counts tries already made, including the one that just failed."""
    if retryable and attempts < max_attempts:
        return "retry"
    return "dead_letter"
