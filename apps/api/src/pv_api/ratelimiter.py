"""Applies the rate limit policies and turns an exceeded limit into a structured error."""

from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_domain.failures import FailureClass
from pv_domain.ratelimit import RatePolicy
from pv_persistence.rate_limit import hit


class RateLimiter:
    def __init__(self, engine: Engine, policies: dict[str, RatePolicy]) -> None:
        self._engine = engine
        self._policies = policies

    def check(self, policy_name: str, subject: str) -> None:
        """Count one hit for the subject. Raises a 429 ApiError when over the limit."""
        policy = self._policies[policy_name]
        hits, retry_after = hit(self._engine, f"{policy.name}:{subject}", policy.window_seconds)
        if hits > policy.limit:
            raise ApiError(
                429,
                "RATE_LIMITED",
                "Too many attempts. Please wait a moment and try again.",
                failure_class=FailureClass.TRANSIENT,
                retry_after_seconds=retry_after,
            )
