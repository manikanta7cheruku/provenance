"""What the API may truthfully say about email delivery.

Mail is queued, then sent by the worker. The API therefore never says "we sent it".
The hint depends only on configuration, never on whether an account exists, so it
cannot be used to find out which addresses are registered.
"""

from dataclasses import dataclass
from typing import Literal

from pv_config import Settings

Mode = Literal["log", "smtp_dev", "smtp"]


@dataclass(frozen=True)
class DeliveryHint:
    mode: Mode
    text: str


def delivery_hint(settings: Settings) -> DeliveryHint:
    if not settings.smtp_host:
        return DeliveryHint(
            "log",
            "Development mode: email is not sent. It is written to the worker log "
            "(docker compose logs worker).",
        )
    if settings.environment != "production":
        return DeliveryHint(
            "smtp_dev",
            "The email is queued. In development, open the local inbox at "
            f"{settings.dev_inbox_url}.",
        )
    return DeliveryHint(
        "smtp",
        "The email is queued and usually arrives within a minute. Check your spam folder "
        "if it does not.",
    )
