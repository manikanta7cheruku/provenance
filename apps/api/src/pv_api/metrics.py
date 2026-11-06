"""Recent request statistics, kept in this process only.

The admin console shows the API's error rate and slowest requests over the last fifteen minutes.
Each API process keeps its own window in memory (a bounded deque of status and duration), so the
numbers describe the process that answered, not a fleet. That is enough while there is one API
process, and the screen says so. A metrics store shared by every process is a carryover for the
deployment checkpoint (3.7).

Nothing here holds a path, a user or a request body: only a time, a status class and a duration.
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass

WINDOW_SECONDS = 15 * 60
MAX_SAMPLES = 5000


@dataclass(frozen=True)
class RequestStatsSnapshot:
    window_seconds: int
    requests: int
    server_errors: int
    client_errors: int
    p50_ms: int | None
    p95_ms: int | None


class RequestStats:
    def __init__(
        self, window_seconds: int = WINDOW_SECONDS, max_samples: int = MAX_SAMPLES
    ) -> None:
        self._window = window_seconds
        self._samples: deque[tuple[float, int, float]] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def record(self, status: int, duration_ms: float, *, now: float | None = None) -> None:
        with self._lock:
            self._samples.append((time.monotonic() if now is None else now, status, duration_ms))

    def snapshot(self, *, now: float | None = None) -> RequestStatsSnapshot:
        moment = time.monotonic() if now is None else now
        with self._lock:
            recent = [(s, d) for t, s, d in self._samples if moment - t <= self._window]
        durations = sorted(d for _s, d in recent)
        return RequestStatsSnapshot(
            window_seconds=self._window,
            requests=len(recent),
            server_errors=sum(1 for s, _d in recent if s >= 500),
            client_errors=sum(1 for s, _d in recent if 400 <= s < 500),
            p50_ms=_percentile(durations, 0.50),
            p95_ms=_percentile(durations, 0.95),
        )


def _percentile(sorted_values: list[float], fraction: float) -> int | None:
    """The nearest-rank percentile, or None when nothing was measured."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return round(sorted_values[rank - 1])
