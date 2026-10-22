"""What a task handler can rely on, and how it reports failure."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Engine

from pv_config import Settings
from pv_mail import Mailer


class TaskFailure(Exception):
    """Raise this from a handler to fail the attempt.

    retryable=True   a later attempt may succeed (network trouble, provider busy)
    retryable=False  retrying cannot help (bad input, recipient does not exist)

    Keep the message free of emails, tokens and user content: it is stored (truncated and
    redacted) and shown to administrators.
    """

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class TaskContext:
    task_id: uuid.UUID
    task_type: str
    args: dict[str, Any]
    secret: dict[str, Any]
    attempt: int
    max_attempts: int
    owner_user_id: uuid.UUID | None
    run_id: uuid.UUID | None
    settings: Settings
    engine: Engine
    mailer: Mailer
    extend_lease: Callable[[], bool]


Handler = Callable[[TaskContext], None]
