"""Run the seed job postings through a real model and print what survived the checks.

    uv run python scripts/eval_seed.py

Needs GEMINI_API_KEY and LLM_MODEL in the environment (the same names as .env). It makes one to two
model calls per posting and stores nothing. It prints, per posting, how many facts and requirements
the model proposed, how many the grounding checks kept, and whether the facts the fixture expects
were found. Those counts are the "failures as data" the evaluation plan asks for: compare them
between prompt versions and models. They are NOT accuracy: the postings are synthetic and the
expected lists were written for a scripted model. Real labeled cases arrive in checkpoint 3.6.

Exit code 2 when the AI is not configured.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from job_fixtures import FIXTURES  # noqa: E402

from pv_config import get_settings  # noqa: E402
from pv_domain.job import PROMPT_VERSION  # noqa: E402
from pv_llm import LLMError, build_provider, extract_job_text  # noqa: E402


def main() -> int:
    settings = get_settings()
    if not settings.gemini_api_key.get_secret_value() or not settings.llm_model:
        print("GEMINI_API_KEY and LLM_MODEL must be set. See .env.example.")
        return 2
    provider = build_provider(settings)
    print(f"prompt {PROMPT_VERSION}, model {settings.llm_model}, {len(FIXTURES)} postings\n")
    print(f"{'posting':44} {'reqs kept':>9} {'dropped':>8} {'facts':>6} {'missing facts'}")
    totals = [0, 0, 0]
    for fixture in FIXTURES:
        try:
            outcome = extract_job_text(
                provider, model=settings.llm_model, posting_text=fixture.text
            )
        except LLMError as exc:
            print(f"{fixture.key:44} failed: {exc.summary}")
            continue
        grounded = outcome.grounded
        missing = sorted(fixture.fact_keys - set(grounded.facts))
        print(
            f"{fixture.key:44} {len(grounded.requirements):>9} {grounded.requirements_dropped:>8} "
            f"{len(grounded.facts):>6} {', '.join(missing) or '-'}"
        )
        totals[0] += len(grounded.requirements)
        totals[1] += grounded.requirements_dropped
        totals[2] += grounded.facts_dropped
    kept, dropped, facts_dropped = totals
    share = dropped / (kept + dropped) if kept + dropped else 0.0
    print(f"\nrequirements kept {kept}, dropped {dropped} ({share:.0%})")
    print(f"facts dropped {facts_dropped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
