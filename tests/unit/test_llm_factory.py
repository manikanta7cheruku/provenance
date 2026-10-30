"""Turning settings into a provider, and knowing when meaning search can work."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import SecretStr

from pv_config import Settings
from pv_llm import GeminiProvider, LLMError, build_provider, embeddings_configured

Make = Callable[..., Settings]


def test_embeddings_need_both_a_key_and_an_embedding_model(make_settings: Make) -> None:
    assert not embeddings_configured(make_settings())
    assert not embeddings_configured(make_settings(gemini_api_key=SecretStr("k")))
    assert not embeddings_configured(make_settings(llm_embedding_model="m"))
    assert embeddings_configured(
        make_settings(gemini_api_key=SecretStr("k"), llm_embedding_model="m")
    )


@pytest.mark.parametrize("for_embeddings", [False, True])
def test_an_unconfigured_provider_is_a_non_retryable_error(
    make_settings: Make, for_embeddings: bool
) -> None:
    with pytest.raises(LLMError) as caught:
        build_provider(make_settings(), for_embeddings=for_embeddings)
    assert caught.value.retryable is False


def test_generation_and_embedding_check_their_own_model_setting(make_settings: Make) -> None:
    only_generation = make_settings(gemini_api_key=SecretStr("k"), llm_model="g")
    assert isinstance(build_provider(only_generation), GeminiProvider)
    with pytest.raises(LLMError):
        build_provider(only_generation, for_embeddings=True)
    only_embedding = make_settings(gemini_api_key=SecretStr("k"), llm_embedding_model="e")
    assert isinstance(build_provider(only_embedding, for_embeddings=True), GeminiProvider)
    with pytest.raises(LLMError):
        build_provider(only_embedding)


def test_the_base_url_is_configuration_not_code(make_settings: Make) -> None:
    settings = make_settings(
        gemini_api_key=SecretStr("k"), llm_model="g", gemini_base_url="http://proxy.local/v1beta/"
    )
    provider: Any = build_provider(settings)
    assert provider._base_url == "http://proxy.local/v1beta"
    default = make_settings()
    assert default.gemini_base_url == "https://generativelanguage.googleapis.com/v1beta"
