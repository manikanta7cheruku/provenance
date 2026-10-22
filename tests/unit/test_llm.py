from collections.abc import Callable
from typing import Any

import httpx
import pytest

from pv_config import Settings
from pv_llm import GeminiProvider, LLMError, content_hash
from pv_llm.check import run

Make = Callable[..., Settings]


def _provider(handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any) -> GeminiProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiProvider("test-key", client=client, **kwargs)


def test_missing_key_is_rejected() -> None:
    with pytest.raises(LLMError):
        GeminiProvider("")


def test_list_models_reads_pages_and_methods() -> None:
    pages = {
        "": {
            "models": [{"name": "models/a", "supportedGenerationMethods": ["generateContent"]}],
            "nextPageToken": "next",
        },
        "next": {"models": [{"name": "models/b", "supportedGenerationMethods": ["embedContent"]}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        return httpx.Response(200, json=pages[request.url.params.get("pageToken", "")])

    models = _provider(handler).list_models()
    assert [m.name for m in models] == ["a", "b"]
    assert models[0].can_generate and not models[0].can_embed
    assert models[1].can_embed


def test_generate_parses_text_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models/some-model:generateContent")
        body = request.read().decode()
        assert "responseMimeType" in body
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "O"}, {"text": "K"}]}}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2},
            },
        )

    result = _provider(handler).generate(model="some-model", prompt="hi", json_output=True)
    assert result.text == "OK"
    assert (result.input_tokens, result.output_tokens) == (7, 2)


def test_embed_returns_the_vector_and_requests_the_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(":embedContent")
        assert '"outputDimensionality":3' in request.read().decode().replace(" ", "")
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2, 0.3]}})

    result = _provider(handler).embed(model="e", text="t", dimensions=3)
    assert result.values == [0.1, 0.2, 0.3]


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (503, True), (400, False), (403, False)]
)
def test_http_errors_are_classified(status: int, retryable: bool) -> None:
    provider = _provider(lambda request: httpx.Response(status, json={"error": "secret echo"}))
    with pytest.raises(LLMError) as caught:
        provider.generate(model="m", prompt="p")
    assert caught.value.retryable is retryable
    assert "secret echo" not in caught.value.summary


def test_no_candidates_is_not_retryable() -> None:
    provider = _provider(lambda request: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(LLMError) as caught:
        provider.generate(model="m", prompt="p")
    assert caught.value.retryable is False


def test_timeouts_are_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError) as caught:
        _provider(handler).generate(model="m", prompt="p")
    assert caught.value.retryable is True


def test_throttle_keeps_a_minimum_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("pv_llm.gemini.time.sleep", sleeps.append)
    monkeypatch.setattr("pv_llm.gemini.time.monotonic", lambda: 100.0)
    provider = _provider(lambda r: httpx.Response(200, json={"models": []}), min_interval_seconds=5)
    provider.list_models()
    provider.list_models()
    assert sleeps == [5.0]


def test_content_hash_separates_parts() -> None:
    assert content_hash("ab", "c") != content_hash("a", "bc")
    assert content_hash("x") == content_hash("x")


def test_check_reports_not_configured_without_a_key(
    make_settings: Make, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(make_settings()) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().out
