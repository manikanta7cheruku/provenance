"""One model call that must return JSON matching a Pydantic schema, with one guided retry.

The retry message tells the model WHERE its answer was wrong (field paths and error kinds),
never WHAT it wrote, so no resume or job text is repeated back into a second prompt.
"""

import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from pv_llm.base import GenerationResult, LLMError, LLMProvider

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class StructuredOutputError(LLMError):
    """The model answered twice and neither answer matched the schema."""

    def __init__(self, calls: list[GenerationResult]) -> None:
        super().__init__("The model did not return valid structured output.", retryable=False)
        self.calls = calls


@dataclass
class StructuredResult[T: BaseModel]:
    value: T
    # Every call made, so the caller can record each one in the usage ledger.
    calls: list[GenerationResult] = field(default_factory=list)
    retried: bool = False


def _parse[T: BaseModel](text: str, schema: type[T]) -> T:
    cleaned = text.strip()
    fenced = _FENCE.match(cleaned)
    if fenced:
        cleaned = fenced.group(1)
    return schema.model_validate(json.loads(cleaned))


def _feedback(exc: Exception) -> str:
    """Describe the failure without quoting any value from the model's answer."""
    if isinstance(exc, ValidationError):
        problems = sorted(
            {f"{'.'.join(str(p) for p in e['loc']) or 'root'} ({e['type']})" for e in exc.errors()}
        )
        return "These parts did not match the required format: " + ", ".join(problems[:12]) + "."
    return "The answer was not valid JSON."


def generate_structured[T: BaseModel](
    provider: LLMProvider,
    *,
    model: str,
    system: str,
    prompt: str,
    schema: type[T],
) -> StructuredResult[T]:
    calls: list[GenerationResult] = []
    first = provider.generate(model=model, prompt=prompt, system=system, json_output=True)
    calls.append(first)
    try:
        return StructuredResult(_parse(first.text, schema), calls)
    except (ValueError, ValidationError) as exc:
        problem = _feedback(exc)
    retry_prompt = (
        f"{prompt}\n\nYour previous answer was rejected. {problem} "
        "Answer again with only the corrected JSON object."
    )
    second = provider.generate(model=model, prompt=retry_prompt, system=system, json_output=True)
    calls.append(second)
    try:
        return StructuredResult(_parse(second.text, schema), calls, retried=True)
    except (ValueError, ValidationError) as exc:
        raise StructuredOutputError(calls) from exc
