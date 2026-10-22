"""The interface the rest of the system depends on. No provider detail leaks through it."""

from dataclasses import dataclass, field
from typing import Protocol


class LLMError(Exception):
    """A model call failed. `retryable` tells the worker whether trying again can help."""

    def __init__(self, summary: str, *, retryable: bool, status_code: int | None = None) -> None:
        super().__init__(summary)
        self.summary = summary
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    input_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class ModelInfo:
    name: str
    methods: list[str] = field(default_factory=list)

    @property
    def can_generate(self) -> bool:
        return "generateContent" in self.methods

    @property
    def can_embed(self) -> bool:
        return "embedContent" in self.methods


class LLMProvider(Protocol):
    name: str

    def list_models(self) -> list[ModelInfo]: ...

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        json_output: bool = False,
        temperature: float = 0.0,
    ) -> GenerationResult: ...

    def embed(self, *, model: str, text: str, dimensions: int | None = None) -> EmbeddingResult: ...
