"""Run the suites, compare with the baseline, and make the report that is stored and shown.

A report is plain JSON: when it was made, which dataset and which versions of our rules and prompts
it was made with, the git commit, every metric with its limit and its baseline, and the cases that
failed (expected and got). It holds no personal data because the dataset is synthetic. Passing
cases are counted, not stored: a failure is what someone needs to open.
"""

import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pv_domain.analysis import SCORING_VERSION
from pv_domain.eligibility import RULES_VERSION as ELIGIBILITY_VERSION
from pv_domain.evaluation import CaseResult, Change, Metric, compare, failing, passed
from pv_domain.job import PROMPT_VERSION as EXTRACT_PROMPT
from pv_domain.preparation import RULES_VERSION as PREP_VERSION
from pv_eval import suites
from pv_eval.dataset import DATASET_VERSION, JobCase, build_jobs

SUITE_DETERMINISTIC = "deterministic"
SUITE_LLM = "llm"
MAX_STORED_FAILURES = 200
ROOT = Path(__file__).resolve().parents[4]
BASELINE_PATH = ROOT / "evaluation" / "baseline.json"
DATASET_PATH = ROOT / "evaluation" / "dataset" / f"{DATASET_VERSION}.json"


def versions() -> dict[str, str]:
    """The versions a result depends on, so two reports can be compared fairly."""
    return {
        "dataset": DATASET_VERSION,
        "scoring": SCORING_VERSION,
        "eligibility_rules": ELIGIBILITY_VERSION,
        "extraction_prompt": EXTRACT_PROMPT,
        "preparation_rules": PREP_VERSION,
    }


def git_sha() -> str | None:
    """The commit this ran against, or None when it cannot be known."""
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env[:10]
    try:
        out = subprocess.run(  # noqa: S603 - fixed arguments, no user input
            ["git", "rev-parse", "--short=10", "HEAD"],  # noqa: S607
            capture_output=True, text=True, timeout=5, cwd=ROOT, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha or None


def run_deterministic(
    jobs: Sequence[JobCase] | None = None,
) -> tuple[list[Metric], list[CaseResult], dict[str, int]]:
    """Every deterministic suite. Returns the metrics, every case result and the case count per suite."""
    data = tuple(jobs) if jobs is not None else build_jobs()
    outputs = {
        "extraction": suites.run_extraction(data),
        "eligibility": suites.run_eligibility(),
        "verdicts": suites.run_verdicts(),
        "bands": suites.run_bands(),
        "ranking": suites.run_ranking(),
        "claims": suites.run_claims(),
    }
    metrics = [m for out in outputs.values() for m in out.metrics]
    results = [r for out in outputs.values() for r in out.results]
    counts = {name: len(out.results) for name, out in outputs.items()}
    return metrics, results, counts


def load_baseline(suite: str = SUITE_DETERMINISTIC, path: Path = BASELINE_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data.get(suite, {}).get("metrics", {}).items()}


def save_baseline(
    metrics: Sequence[Metric], suite: str = SUITE_DETERMINISTIC, path: Path = BASELINE_PATH
) -> None:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[suite] = {
        "dataset_version": DATASET_VERSION,
        "versions": versions(),
        "metrics": {m.name: round(m.value, 4) for m in metrics},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _change(c: Change, cases: int, suite: str) -> dict[str, Any]:
    d = asdict(c)
    d["cases"] = cases
    d["suite"] = suite
    return d


def build_report(
    suite: str,
    metrics: Sequence[Metric],
    results: Sequence[CaseResult],
    counts: dict[str, int],
    baseline: dict[str, float],
    *,
    now: datetime | None = None,
    sha: str | None = None,
    model: str | None = None,
    extra_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    changes = compare(metrics, baseline)
    by_name = {m.name: m for m in metrics}
    failed_cases = [r for r in results if not r.passed]
    per_suite = {
        name: {"cases": total, "failed": sum(1 for r in failed_cases if r.suite == name)}
        for name, total in counts.items()
    }
    return {
        "suite": suite,
        "created_at": (now or datetime.now(UTC)).isoformat(),
        "git_sha": sha if sha is not None else git_sha(),
        "dataset_version": DATASET_VERSION,
        "model": model,
        "versions": {**versions(), **(extra_versions or {})},
        "passed": passed(changes),
        "metrics": [_change(c, by_name[c.name].cases, by_name[c.name].suite) for c in changes],
        "suites": per_suite,
        "regressions": [c.name for c in failing(changes)],
        "failures": [asdict(r) for r in failed_cases[:MAX_STORED_FAILURES]],
        "failure_count": len(failed_cases),
        "case_count": sum(counts.values()),
    }


def deterministic_report(**kwargs: Any) -> dict[str, Any]:
    metrics, results, counts = run_deterministic()
    return build_report(SUITE_DETERMINISTIC, metrics, results, counts, load_baseline(), **kwargs)


def dataset_snapshot() -> dict[str, Any]:
    from pv_eval.dataset import to_data

    return to_data(build_jobs())


def write_dataset(path: Path = DATASET_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dataset_snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def table(report: dict[str, Any]) -> str:
    """The report as text for a terminal."""
    lines = [
        f"{report['suite']} suite, dataset {report['dataset_version']}, commit {report['git_sha'] or 'unknown'}",
        f"{'metric':36} {'value':>8} {'baseline':>9} {'limit':>7}  status",
    ]
    for m in report["metrics"]:
        base = "-" if m["baseline"] is None else f"{m['baseline']:.4f}"
        arrow = ">=" if m["direction"] == "higher" else "<="
        lines.append(
            f"{m['name']:36} {m['value']:8.4f} {base:>9} {arrow}{m['limit']:5.2f}  {m['status']}"
        )
    lines.append(
        f"{report['case_count']} cases, {report['failure_count']} failed. "
        + ("PASSED" if report["passed"] else "FAILED: " + ", ".join(report["regressions"]))
    )
    return "\n".join(lines)
