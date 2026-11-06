"""Command line for the evaluation harness.

  python -m pv_eval run                 the deterministic suites (free, no model, what CI runs)
  python -m pv_eval run --store         ... and record the report so the admin console can show it
  python -m pv_eval run --llm           the LLM suite against the real model (costs tokens)
  python -m pv_eval run --update-baseline   accept today's numbers as the new baseline (a decision)
  python -m pv_eval dataset             what the dataset holds
  python -m pv_eval write-dataset       rebuild evaluation/dataset/jobs-v1.json

Exit code 0 when every metric is inside its limit and no worse than its baseline, 1 when not, 2
when the model is not configured for --llm.
"""

import argparse
import json
import sys
from pathlib import Path

from pv_eval import report as rep
from pv_eval.dataset import build_jobs, summarize


def _run(args: argparse.Namespace) -> int:
    if args.llm:
        return _run_llm(args)
    report = rep.deterministic_report()
    metrics, _results, _counts = rep.run_deterministic()
    print(rep.table(report))
    if args.update_baseline:
        rep.save_baseline(metrics)
        print(f"Baseline written to {rep.BASELINE_PATH}. Review the change before committing it.")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.store:
        _store(report)
    return 0 if report["passed"] or args.update_baseline else 1


def _run_llm(args: argparse.Namespace) -> int:
    from pv_config import get_settings
    from pv_llm import LLMError, build_provider, extract_job_text

    settings = get_settings()
    if not settings.gemini_api_key.get_secret_value() or not settings.llm_model:
        print("GEMINI_API_KEY and LLM_MODEL must be set. See .env.example.")
        return 2
    provider = build_provider(settings)
    jobs = build_jobs()[: args.limit] if args.limit else build_jobs()

    def extract(text: str):  # type: ignore[no-untyped-def]
        try:
            return extract_job_text(provider, model=settings.llm_model, posting_text=text).grounded
        except LLMError as exc:
            raise RuntimeError(exc.summary) from exc

    from pv_eval.llm import run_llm_extraction

    metrics, results, counts = run_llm_extraction(jobs, extract)
    report = rep.build_report(
        rep.SUITE_LLM,
        metrics,
        results,
        counts,
        rep.load_baseline(rep.SUITE_LLM),
        model=settings.llm_model,
    )
    print(rep.table(report))
    if args.update_baseline:
        rep.save_baseline(metrics, rep.SUITE_LLM)
        print("LLM baseline written.")
    if args.store:
        _store(report)
    # With no baseline there is nothing to regress from, and the limits are starting points.
    return 0 if report["passed"] or not rep.load_baseline(rep.SUITE_LLM) else 1


def _store(report: dict) -> None:  # type: ignore[type-arg]
    from pv_config import get_settings
    from pv_persistence.engine import create_db_engine
    from pv_persistence.evaluation import record_run

    engine = create_db_engine(get_settings().database_url.get_secret_value())
    run_id = record_run(engine, report, trigger="manual")
    print(f"Stored as run {run_id}. Open Admin, Evaluation to see it.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pv_eval")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the suites and compare with the baseline")
    run.add_argument(
        "--llm", action="store_true", help="run the LLM suite (needs a model key, costs tokens)"
    )
    run.add_argument("--limit", type=int, default=0, help="with --llm, only the first N postings")
    run.add_argument("--store", action="store_true", help="record the report in the database")
    run.add_argument("--json", default="", help="also write the report to this file")
    run.add_argument(
        "--update-baseline", action="store_true", help="accept these numbers as the baseline"
    )
    sub.add_parser("dataset", help="show what the dataset holds")
    sub.add_parser("write-dataset", help="rebuild the saved dataset file")
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "dataset":
        s = summarize(build_jobs())
        print(
            f"{s.version}: {s.jobs} postings, {s.requirements} labeled requirements, {s.facts} labeled facts"
        )
        for tag, n in s.tags.items():
            print(f"  {tag}: {n}")
        return 0
    rep.write_dataset()
    print(f"Wrote {rep.DATASET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
