"""Check the AI provider setup. Run: python -m pv_llm.check

1. lists the models your key can use (names only, never the key)
2. tests one generation with LLM_MODEL
3. tests one embedding with LLM_EMBEDDING_MODEL and LLM_EMBEDDING_DIMENSIONS

Model names are configuration. This tool exists so you never have to guess a name.
Exit code: 0 all configured checks passed, 1 a check failed, 2 not configured.
"""

import sys

from pv_config import Settings, get_settings
from pv_llm.base import LLMError
from pv_llm.gemini import GeminiProvider


def run(settings: Settings) -> int:
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        print("GEMINI_API_KEY is not set. Create a key in Google AI Studio and put it in .env.")
        return 2
    provider = GeminiProvider(key, min_interval_seconds=settings.llm_min_interval_seconds)
    failed = False

    try:
        models = provider.list_models()
    except LLMError as exc:
        print(f"FAIL listing models: {exc.summary}")
        return 1
    generate_names = sorted(m.name for m in models if m.can_generate)
    embed_names = sorted(m.name for m in models if m.can_embed)
    print(f"Models that support generateContent ({len(generate_names)}):")
    for name in generate_names:
        print(f"  {name}")
    print(f"Models that support embedContent ({len(embed_names)}):")
    for name in embed_names:
        print(f"  {name}")

    if not settings.llm_model:
        print("\nLLM_MODEL is not set. Pick a name from the first list and put it in .env.")
        return 2
    if settings.llm_model not in generate_names:
        print(f"\nFAIL: LLM_MODEL={settings.llm_model} is not in the generateContent list.")
        failed = True
    else:
        try:
            result = provider.generate(model=settings.llm_model, prompt="Reply with the word OK.")
            print(
                f"\nOK generation with {settings.llm_model}: {result.latency_ms} ms, "
                f"{result.input_tokens} input tokens, {result.output_tokens} output tokens"
            )
        except LLMError as exc:
            print(f"\nFAIL generation: {exc.summary}")
            failed = True

    if not settings.llm_embedding_model:
        print("LLM_EMBEDDING_MODEL is not set. Embeddings are optional until checkpoint 1.5.")
    elif settings.llm_embedding_model not in embed_names:
        print(
            f"FAIL: LLM_EMBEDDING_MODEL={settings.llm_embedding_model} "
            "is not in the embedContent list."
        )
        failed = True
    else:
        try:
            embedding = provider.embed(
                model=settings.llm_embedding_model,
                text="Provenance embedding check",
                dimensions=settings.llm_embedding_dimensions,
            )
            size = len(embedding.values)
            if size != settings.llm_embedding_dimensions:
                print(
                    f"FAIL embedding: got {size} numbers but LLM_EMBEDDING_DIMENSIONS="
                    f"{settings.llm_embedding_dimensions}. They must match."
                )
                failed = True
            else:
                print(f"OK embedding with {settings.llm_embedding_model}: {size} dimensions")
        except LLMError as exc:
            print(f"FAIL embedding: {exc.summary}")
            failed = True
    return 1 if failed else 0


def main() -> int:
    return run(get_settings())


if __name__ == "__main__":
    sys.exit(main())
