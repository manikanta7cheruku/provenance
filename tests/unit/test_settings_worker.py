from collections.abc import Callable

import pytest
from pydantic import ValidationError

from pv_config import Settings

Make = Callable[..., Settings]


def test_worker_defaults(make_settings: Make) -> None:
    s = make_settings()
    assert s.worker_poll_interval_seconds == 1.0
    assert s.worker_lease_seconds > s.worker_heartbeat_seconds
    assert s.llm_embedding_dimensions == 768
    assert s.gemini_api_key.get_secret_value() == ""
    assert s.llm_model == ""


def test_model_names_and_prices_default_to_nothing_invented(make_settings: Make) -> None:
    s = make_settings()
    assert s.llm_model == ""
    assert s.llm_embedding_model == ""
    assert s.llm_input_price_per_million == 0.0
    assert s.llm_output_price_per_million == 0.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"worker_lease_seconds": 10, "worker_heartbeat_seconds": 10},
        {"worker_lease_seconds": 5},
        {"worker_poll_interval_seconds": 0},
        {"worker_heartbeat_seconds": 0},
        {"llm_input_price_per_million": -1},
        {"llm_min_interval_seconds": -0.5},
        {"llm_embedding_dimensions": 0},
    ],
)
def test_invalid_worker_and_llm_values_are_rejected(
    make_settings: Make, overrides: dict[str, float]
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**overrides)


def test_gemini_key_is_not_printed(make_settings: Make) -> None:
    s = make_settings(gemini_api_key="super-secret-key")
    assert "super-secret-key" not in repr(s)
