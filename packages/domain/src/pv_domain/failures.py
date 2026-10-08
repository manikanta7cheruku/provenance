"""Failure classification shared by every part of the system.

Every failure carries three layers: the technical error, a recoverability class
(this enum) and a user-facing explanation. See docs/architecture/architecture.md
section 10.
"""

from enum import StrEnum


class FailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SECURITY_REJECTED = "SECURITY_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_AUTO_RETRYABLE = frozenset({FailureClass.TRANSIENT, FailureClass.SOURCE_UNAVAILABLE})


def is_automatically_retryable(failure_class: FailureClass) -> bool:
    """Whether the task runner may retry without any human action.

    VALIDATION_FAILED is retried only by the extraction logic itself, with
    feedback and a bounded budget, so it is not listed here.
    """
    return failure_class in _AUTO_RETRYABLE
