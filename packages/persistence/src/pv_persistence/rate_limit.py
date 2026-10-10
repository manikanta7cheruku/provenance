"""Fixed-window rate limit counters in PostgreSQL.

Each hit is its own committed transaction, so a failed request still counts.
Known limitation: a fixed window allows a burst at a window boundary. A sliding
window is a later refinement if measurements justify it (ADR-0009).
"""

import math
import secrets

from sqlalchemy import text
from sqlalchemy.engine import Engine

_HIT = text(
    """
    INSERT INTO rate_limit_buckets AS b (bucket_key, window_start, hits)
    VALUES (
        :bucket_key,
        to_timestamp(
            floor(extract(epoch FROM now()) / CAST(:window AS double precision))
            * CAST(:window AS double precision)
        ),
        1
    )
    ON CONFLICT (bucket_key, window_start) DO UPDATE SET hits = b.hits + 1
    RETURNING
        b.hits,
        extract(epoch FROM (
            b.window_start + make_interval(secs => CAST(:window AS double precision)) - now()
        ))
    """
)
_PURGE = text("DELETE FROM rate_limit_buckets WHERE window_start < now() - interval '2 days'")


def hit(engine: Engine, bucket_key: str, window_seconds: int) -> tuple[int, int]:
    """Record one hit. Returns (hits in this window, seconds until the window resets)."""
    with engine.begin() as conn:
        row = conn.execute(_HIT, {"bucket_key": bucket_key, "window": window_seconds}).one()
        if secrets.randbelow(200) == 0:  # opportunistic cleanup, roughly every 200th hit
            conn.execute(_PURGE)
    return int(row[0]), max(1, math.ceil(float(row[1])))
