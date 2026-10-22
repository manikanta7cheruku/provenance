"""Gemini REST implementation (Google AI Studio / Gemini API, version v1beta).

Endpoints used (checked against the official API reference):
  GET  /v1beta/models                       list models and their supportedGenerationMethods
  POST /v1beta/models/{model}:generateContent
  POST /v1beta/models/{model}:embedContent
Authentication is the x-goog-api-key header. The key is never put in a URL or a log line.
Model names are never hardcoded here: they come from configuration.
"""

import threading
import time
from typing import Any

import httpx

from pv_llm.base import EmbeddingResult, GenerationResult, LLMError, ModelInfo

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        min_interval_seconds: float = 0.0,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set.", retryable=False)
        self._base_url = base_url.rstrip("/")
        self._min_interval = min_interval_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        self._lock = threading.Lock()
        self._last_call = 0.0

    def _throttle(self) -> None:
        """Free tiers limit requests per minute: keep a minimum gap between calls."""
        if self._min_interval <= 0:
            return
        with self._lock:
            wait = self._last_call + self._min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _send(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        try:
            response = self._client.request(
                method, f"{self._base_url}{path}", headers=self._headers, json=body
            )
        except httpx.TimeoutException as exc:
            raise LLMError("The model provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Could not reach the model provider ({type(exc).__name__}).", retryable=True
            ) from exc
        if response.status_code >= 400:
            # The provider's error body is not copied: it can echo request content.
            raise LLMError(
                f"The model provider answered HTTP {response.status_code}.",
                retryable=response.status_code in _RETRYABLE_STATUS,
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError(
                "The model provider returned an unreadable answer.", retryable=True
            ) from exc
        if not isinstance(data, dict):
            raise LLMError("The model provider returned an unexpected answer.", retryable=True)
        return data

    def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        token: str | None = None
        for _ in range(20):  # a hard page limit: never loop forever on a misbehaving server
            query = "?pageSize=1000" + (f"&pageToken={token}" if token else "")
            data = self._send("GET", f"/models{query}")
            for item in data.get("models", []):
                name = str(item.get("name", "")).removeprefix("models/")
                if name:
                    methods = list(item.get("supportedGenerationMethods", []))
                    models.append(ModelInfo(name=name, methods=methods))
            token = data.get("nextPageToken")
            if not token:
                break
        return models

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        json_output: bool = False,
        temperature: float = 0.0,
    ) -> GenerationResult:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_output:
            body["generationConfig"]["responseMimeType"] = "application/json"
        started = time.perf_counter()
        data = self._send("POST", f"/models/{model}:generateContent", body)
        latency_ms = round((time.perf_counter() - started) * 1000)
        candidates = data.get("candidates") or []
        if not candidates:
            # No candidate usually means the prompt was blocked. Retrying will not change that.
            raise LLMError("The model returned no answer.", retryable=False)
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(str(part.get("text", "")) for part in parts)
        usage = data.get("usageMetadata") or {}
        return GenerationResult(
            text=text,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
            latency_ms=latency_ms,
        )

    def embed(self, *, model: str, text: str, dimensions: int | None = None) -> EmbeddingResult:
        body: dict[str, Any] = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": text}]},
        }
        if dimensions:
            body["outputDimensionality"] = dimensions
        started = time.perf_counter()
        data = self._send("POST", f"/models/{model}:embedContent", body)
        latency_ms = round((time.perf_counter() - started) * 1000)
        values = (data.get("embedding") or {}).get("values")
        if not isinstance(values, list) or not values:
            raise LLMError("The embedding answer had no vector.", retryable=False)
        usage = data.get("usageMetadata") or {}
        return EmbeddingResult(
            values=[float(v) for v in values],
            input_tokens=int(usage.get("promptTokenCount", 0)),
            latency_ms=latency_ms,
        )
