import pytest

from pv_domain.cost import estimate_cost_usd
from pv_domain.redaction import MAX_ERROR_LENGTH, error_summary, redact
from pv_domain.retry import backoff_seconds, decide_after_failure


@pytest.mark.parametrize("attempt", range(1, 12))
def test_backoff_stays_between_half_the_ceiling_and_the_ceiling(attempt: int) -> None:
    ceiling = min(300.0, 5.0 * 2 ** (attempt - 1))
    low = backoff_seconds(attempt, rand=lambda: 0.0)
    high = backoff_seconds(attempt, rand=lambda: 1.0)
    assert low == pytest.approx(ceiling / 2)
    assert high == pytest.approx(ceiling)


def test_backoff_is_capped_and_never_overflows() -> None:
    assert backoff_seconds(10_000, rand=lambda: 1.0) == 300.0


def test_backoff_grows_exponentially_before_the_cap() -> None:
    delays = [backoff_seconds(n, rand=lambda: 1.0) for n in (1, 2, 3, 4)]
    assert delays == [5.0, 10.0, 20.0, 40.0]


def test_backoff_rejects_attempt_zero() -> None:
    with pytest.raises(ValueError):
        backoff_seconds(0)


def test_real_random_source_stays_in_range() -> None:
    for _ in range(50):
        assert 2.5 <= backoff_seconds(1) <= 5.0


@pytest.mark.parametrize(
    ("attempts", "max_attempts", "retryable", "expected"),
    [
        (1, 5, True, "retry"),
        (4, 5, True, "retry"),
        (5, 5, True, "dead_letter"),
        (1, 5, False, "dead_letter"),
        (1, 1, True, "dead_letter"),
    ],
)
def test_decide_after_failure(
    attempts: int, max_attempts: int, retryable: bool, expected: str
) -> None:
    assert decide_after_failure(attempts, max_attempts, retryable=retryable) == expected


def test_redact_removes_emails_and_token_like_strings() -> None:
    text = "failed for ada@example.com with token " + "A1b2C3d4" * 6
    cleaned = redact(text)
    assert "@" not in cleaned
    assert "A1b2C3d4" not in cleaned
    assert "[email]" in cleaned


def test_error_summary_is_truncated_to_the_limit() -> None:
    summary = error_summary("SomeError", "x " * 1000)
    assert len(summary) <= MAX_ERROR_LENGTH
    assert summary.endswith("...")


def test_error_summary_keeps_short_messages_whole() -> None:
    assert error_summary("TaskFailure", "SMTP error 550") == "TaskFailure: SMTP error 550"


def test_cost_uses_per_million_prices() -> None:
    cost = estimate_cost_usd(
        1_000_000, 500_000, input_price_per_million=0.5, output_price_per_million=2.0
    )
    assert str(cost) == "1.500000"


def test_cost_defaults_to_zero_when_prices_are_zero() -> None:
    assert estimate_cost_usd(123, 456, input_price_per_million=0, output_price_per_million=0) == 0
