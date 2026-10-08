import pytest

from pv_domain.failures import FailureClass, is_automatically_retryable


@pytest.mark.parametrize(
    ("failure_class", "expected"),
    [
        (FailureClass.TRANSIENT, True),
        (FailureClass.SOURCE_UNAVAILABLE, True),
        (FailureClass.PERMANENT, False),
        (FailureClass.USER_ACTION_REQUIRED, False),
        (FailureClass.QUOTA_EXCEEDED, False),
        (FailureClass.VALIDATION_FAILED, False),
        (FailureClass.SECURITY_REJECTED, False),
        (FailureClass.INTERNAL_ERROR, False),
    ],
)
def test_retry_policy(failure_class: FailureClass, expected: bool) -> None:
    assert is_automatically_retryable(failure_class) is expected


def test_every_class_has_an_explicit_retry_decision() -> None:
    for failure_class in FailureClass:
        assert isinstance(is_automatically_retryable(failure_class), bool)
