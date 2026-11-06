"""Checkpoint 3.6: the evaluation harness, and the regression gate that runs on every build.

Three kinds of test live here:
  - the metrics and the comparison rules (pure, in pv_domain.evaluation)
  - the dataset: it is rebuilt the same way every time, matches the saved file, and every label is
    true of its text
  - the gate: the deterministic suites must be inside their limits and no worse than the saved
    baseline, and the gate must fail when something is made worse (checked by making it worse)
"""

import json
from datetime import UTC, datetime

import pytest

import pv_domain.job_facts as job_facts
from pv_domain.evaluation import (
    HIGHER,
    LOWER,
    RANKER_MIN_GAIN,
    RANKER_MIN_LABELS,
    RANKER_MIN_PEOPLE,
    Metric,
    compare,
    failing,
    judge,
    pairwise_agreement,
    passed,
    precision_recall,
    ranker_decision,
    rate,
    weighted_error,
)
from pv_domain.job_facts import GroundedJob
from pv_eval import report as rep
from pv_eval import suites
from pv_eval.__main__ import main
from pv_eval.dataset import DATASET_VERSION, JobCase, build_jobs, summarize, to_data
from pv_eval.llm import run_llm_extraction


def metric(
    name: str = "m", value: float = 0.9, direction: str = HIGHER, limit: float = 0.8
) -> Metric:
    return Metric(name, value, direction, limit, 10, "s", name)


# ------------------------------------------------------------------ the arithmetic


def test_rate_treats_nothing_to_check_as_nothing_wrong() -> None:
    assert rate(3, 4) == 0.75 and rate(0, 0) == 1.0


def test_precision_and_recall() -> None:
    assert precision_recall(8, 10, 16) == (0.8, 0.5)
    assert precision_recall(0, 0, 0) == (1.0, 1.0)


def test_a_false_negative_costs_three_times_a_false_positive() -> None:
    assert weighted_error(1, 0, 10) == 0.3
    assert weighted_error(0, 1, 10) == 0.1
    assert weighted_error(0, 0, 0) == 0.0


def test_pairwise_agreement_gives_a_tie_half_credit() -> None:
    assert pairwise_agreement([(2.0, 1.0), (3.0, 1.0)]) == 1.0
    assert pairwise_agreement([(1.0, 2.0)]) == 0.0
    assert pairwise_agreement([(1.0, 1.0)]) == 0.5
    assert pairwise_agreement([]) == 1.0


# ------------------------------------------------------------------ judging a metric


@pytest.mark.parametrize(
    ("direction", "value", "limit", "baseline", "status"),
    [
        (HIGHER, 0.90, 0.80, None, "new"),
        (HIGHER, 0.90, 0.80, 0.90, "ok"),
        (HIGHER, 0.95, 0.80, 0.90, "ok"),  # better than the baseline is fine
        (HIGHER, 0.85, 0.80, 0.90, "regressed"),  # above the limit but worse than before
        (HIGHER, 0.79, 0.80, 0.70, "below_limit"),  # below the limit even though better than before
        (LOWER, 0.00, 0.05, 0.00, "ok"),
        (LOWER, 0.02, 0.05, 0.00, "regressed"),
        (LOWER, 0.06, 0.05, 0.10, "below_limit"),
        (LOWER, 0.00, 0.05, 0.03, "ok"),
    ],
)
def test_a_metric_is_ok_new_regressed_or_below_its_limit(
    direction: str, value: float, limit: float, baseline: float | None, status: str
) -> None:
    assert judge(metric(value=value, direction=direction, limit=limit), baseline).status == status


def test_a_tolerance_lets_noise_through_but_not_a_real_drop() -> None:
    m = metric(value=0.89, limit=0.5)
    assert judge(m, 0.90, tolerance=0.02).status == "ok"
    assert judge(m, 0.95, tolerance=0.02).status == "regressed"


def test_a_run_passes_only_when_nothing_failed() -> None:
    good = compare([metric("a", 0.9), metric("b", 0.9)], {"a": 0.9, "b": 0.9})
    assert passed(good) and failing(good) == ()
    bad = compare([metric("a", 0.9), metric("b", 0.7)], {"a": 0.9, "b": 0.9})
    assert not passed(bad) and [c.name for c in failing(bad)] == ["b"]
    assert passed(compare([metric("a", 0.9)], {}))  # no baseline yet: new, not failed


# ------------------------------------------------------------------ the learned ranker decision


def test_a_learned_ranker_is_refused_with_every_reason_that_applies() -> None:
    decision = ranker_decision(10, 2, 0.9, None)
    assert not decision.adopt and len(decision.reasons) == 3
    assert any(str(RANKER_MIN_LABELS) in r for r in decision.reasons)
    assert any(str(RANKER_MIN_PEOPLE) in r for r in decision.reasons)
    assert any("No candidate" in r for r in decision.reasons)


def test_a_candidate_must_win_by_enough_on_enough_labels_from_enough_people() -> None:
    enough = (RANKER_MIN_LABELS, RANKER_MIN_PEOPLE)
    assert ranker_decision(*enough, 0.90, 0.90 + RANKER_MIN_GAIN).adopt
    small = ranker_decision(*enough, 0.90, 0.92)
    assert not small.adopt and "gain of at least 5%" in small.reasons[0]
    assert not ranker_decision(*enough, 0.90, 0.80).adopt  # worse than the rules
    assert not ranker_decision(RANKER_MIN_LABELS - 1, RANKER_MIN_PEOPLE, 0.9, 0.99).adopt
    assert not ranker_decision(RANKER_MIN_LABELS, RANKER_MIN_PEOPLE - 1, 0.9, 0.99).adopt


# ------------------------------------------------------------------ the dataset


def test_the_dataset_is_the_same_every_time_and_matches_the_saved_file() -> None:
    assert to_data(build_jobs()) == to_data(build_jobs())
    saved = json.loads(rep.DATASET_PATH.read_text(encoding="utf-8"))
    assert saved == to_data(build_jobs()), (
        "The dataset changed. If that is on purpose, bump DATASET_VERSION, run "
        "'python -m pv_eval write-dataset' and update the baseline."
    )
    assert saved["dataset_version"] == DATASET_VERSION


def test_the_dataset_has_a_hundred_postings_with_the_cases_the_plan_asks_for() -> None:
    summary = summarize(build_jobs())
    assert summary.jobs == 100 and summary.requirements > 500 and summary.facts > 500
    for tag in (
        "injection",
        "buried_sponsorship",
        "us_only",
        "remote",
        "entry",
        "senior",
        "internship",
    ):
        assert summary.tags.get(tag, 0) >= 5, tag


def test_every_label_is_true_of_its_posting() -> None:
    for job in build_jobs():
        for r in job.requirements:
            assert r.quote in job.text, (job.case_id, r.quote)
            assert r.kind in ("required", "preferred")
        for key, fact in job.facts.items():
            assert fact.quote in job.text, (job.case_id, key)
        if job.injected:
            assert job.injected in job.text
        assert job.title in job.text and job.company in job.text


def test_case_ids_are_unique_and_postings_differ() -> None:
    jobs = build_jobs()
    assert len({j.case_id for j in jobs}) == 100
    assert len({j.text for j in jobs}) == 100


def test_the_dataset_holds_no_real_looking_personal_data() -> None:
    text = json.dumps(to_data(build_jobs()))
    assert "@" not in text and "http" not in text and "+91" not in text


# ------------------------------------------------------------------ the suites


def test_every_suite_runs_and_returns_metrics_and_cases() -> None:
    metrics, results, counts = rep.run_deterministic()
    assert set(counts) == {"extraction", "eligibility", "verdicts", "bands", "ranking", "claims"}
    assert all(c > 0 for c in counts.values())
    assert len({m.name for m in metrics}) == len(metrics)
    assert sum(counts.values()) == len(results) > 800


def test_the_suites_are_deterministic() -> None:
    a = rep.run_deterministic()
    b = rep.run_deterministic()
    assert [(m.name, m.value) for m in a[0]] == [(m.name, m.value) for m in b[0]]
    assert [(r.case_id, r.passed) for r in a[1]] == [(r.case_id, r.passed) for r in b[1]]


def test_the_known_limit_is_reported_and_not_hidden() -> None:
    _metrics, results, _ = rep.run_deterministic()
    quoted = [r for r in results if r.case_id.endswith("/injection_quoted")]
    assert quoted and all(not r.passed and "Known limit" in r.note for r in quoted)


def test_the_naive_ranker_is_clearly_worse_than_the_shipped_scorer() -> None:
    assert (
        suites.agreement(suites.deterministic_ranker)
        > suites.agreement(suites.met_count_ranker) + 0.2
    )


def test_the_ranking_suite_can_show_a_candidate_losing_or_winning() -> None:
    def reversed_ranker(case: suites.BandCase) -> float:
        return -suites.deterministic_ranker(case)

    assert suites.agreement(reversed_ranker) < 0.1
    assert suites.agreement(suites.deterministic_ranker) > 0.95


# ------------------------------------------------------------------ the gate


def test_the_gate_the_deterministic_suites_are_inside_their_limits_and_no_worse_than_baseline() -> (
    None
):
    report = rep.deterministic_report(now=datetime(2026, 1, 1, tzinfo=UTC), sha="test")
    bad = [m for m in report["metrics"] if m["status"] not in ("ok", "new")]
    assert report["passed"], (
        f"Regressed: {bad}. If this is a real, accepted change run: python -m pv_eval run --update-baseline"
    )
    assert not [m for m in report["metrics"] if m["status"] == "new"], (
        "A metric has no baseline. Run: python -m pv_eval run --update-baseline"
    )


def test_the_baseline_names_exactly_the_metrics_the_suites_produce() -> None:
    metrics, _r, _c = rep.run_deterministic()
    assert set(rep.load_baseline()) == {m.name for m in metrics}


def test_the_gate_fails_when_grounding_is_made_worse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the grounding check keep everything, and the gate must notice."""
    real = job_facts.ground_extraction

    def lax(raw_text: str, proposed: dict[str, object]) -> GroundedJob:
        out = real(raw_text, proposed)
        for item in proposed.get("requirements", []):  # type: ignore[attr-defined]
            if isinstance(item, dict) and item.get("quote") not in {
                r["quote"] for r in out.requirements
            }:
                out.requirements.append({"text": item["text"], "kind": item["kind"], "category": "other",
                                         "years_min": None, "quote": item["quote"], "quote_start": 0, "quote_end": 0})  # fmt: skip
        return out

    monkeypatch.setattr(suites, "ground_extraction", lax)
    report = rep.deterministic_report(now=datetime(2026, 1, 1, tzinfo=UTC), sha="test")
    assert not report["passed"]
    assert (
        "invented_leak_rate" in report["regressions"]
        or "requirement_precision" in report["regressions"]
    )


def test_the_gate_fails_when_eligibility_gets_a_false_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pv_domain.eligibility import EligibilityResult, EligibilityState

    monkeypatch.setattr(
        suites,
        "evaluate_eligibility",
        lambda f, p, y: EligibilityResult(EligibilityState.NOT_ELIGIBLE),
    )
    report = rep.deterministic_report(now=datetime(2026, 1, 1, tzinfo=UTC), sha="test")
    assert not report["passed"]
    assert "eligibility_false_negative_rate" in report["regressions"]
    assert "eligibility_weighted_error" in report["regressions"]


def test_the_gate_fails_when_a_verdict_check_is_loosened(monkeypatch: pytest.MonkeyPatch) -> None:
    from pv_domain.analysis import AcceptedVerdict, EvidenceKind, Verdict

    monkeypatch.setattr(
        suites,
        "accept_verdict",
        lambda proposed, seen: AcceptedVerdict(Verdict.MET, EvidenceKind.DIRECT, (), "", False),
    )
    report = rep.deterministic_report(now=datetime(2026, 1, 1, tzinfo=UTC), sha="test")
    assert "unsupported_verdict_leak_rate" in report["regressions"]


# ------------------------------------------------------------------ the report


def test_the_report_records_what_makes_two_runs_comparable() -> None:
    report = rep.deterministic_report(now=datetime(2026, 1, 1, tzinfo=UTC), sha="abc123")
    assert report["suite"] == "deterministic" and report["git_sha"] == "abc123"
    assert report["dataset_version"] == DATASET_VERSION and report["created_at"].startswith(
        "2026-01-01"
    )
    assert {"scoring", "eligibility_rules", "extraction_prompt", "dataset"} <= set(
        report["versions"]
    )
    first = report["metrics"][0]
    assert {
        "name",
        "label",
        "value",
        "baseline",
        "limit",
        "direction",
        "status",
        "delta",
        "cases",
        "suite",
    } <= set(first)
    assert report["case_count"] == sum(s["cases"] for s in report["suites"].values())
    assert report["failure_count"] == sum(s["failed"] for s in report["suites"].values())


def test_only_failures_are_kept_and_they_are_capped() -> None:
    report = rep.deterministic_report(sha="x")
    assert all(not f.get("passed", False) for f in report["failures"])
    assert len(report["failures"]) <= rep.MAX_STORED_FAILURES
    assert {"suite", "case_id", "expected", "got", "note"} <= set(report["failures"][0])


def test_the_table_is_readable_and_says_passed_or_failed() -> None:
    text = rep.table(rep.deterministic_report(sha="x"))
    assert "metric" in text and "requirement_recall" in text and text.rstrip().endswith("PASSED")


def test_a_baseline_round_trips(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "baseline.json"  # type: ignore[operator]
    metrics = [metric("a", 0.9), metric("b", 0.1, LOWER, 0.2)]
    rep.save_baseline(metrics, path=path)
    assert rep.load_baseline(path=path) == {"a": 0.9, "b": 0.1}
    rep.save_baseline([metric("c", 0.5)], "llm", path=path)
    assert rep.load_baseline("llm", path=path) == {"c": 0.5}
    assert rep.load_baseline(path=path) == {
        "a": 0.9,
        "b": 0.1,
    }  # one suite does not erase the other
    assert rep.load_baseline(path=tmp_path / "missing.json") == {}  # type: ignore[operator]


# ------------------------------------------------------------------ the LLM suite, with stand-in models


def perfect_extract(jobs: tuple[JobCase, ...]):  # type: ignore[no-untyped-def]
    by_text = {j.text: j for j in jobs}

    def extract(text: str) -> GroundedJob:
        case = by_text[text]
        return job_facts.ground_extraction(text, suites._answer(case))

    return extract


def test_a_perfect_model_scores_perfectly_on_the_llm_suite() -> None:
    jobs = build_jobs()[:20]
    metrics, results, _counts = run_llm_extraction(jobs, perfect_extract(jobs))
    values = {m.name: m.value for m in metrics}
    assert values["llm_requirement_recall"] == 1.0 and values["llm_requirement_precision"] == 1.0
    assert values["llm_kind_accuracy"] == 1.0 and values["llm_fact_accuracy"] == 1.0
    assert values["llm_injection_followed_rate"] == 0.0
    assert all(r.passed for r in results)


def test_a_model_that_misses_things_scores_lower_and_the_cases_say_which() -> None:
    jobs = build_jobs()[:20]
    good = perfect_extract(jobs)

    def drops_half(text: str) -> GroundedJob:
        out = good(text)
        out.requirements = out.requirements[::2]
        out.facts = {k: v for k, v in out.facts.items() if k != "sponsorship"}
        return out

    metrics, results, _ = run_llm_extraction(jobs, drops_half)
    values = {m.name: m.value for m in metrics}
    assert (
        0.4 < values["llm_requirement_recall"] < 0.7 and values["llm_requirement_precision"] == 1.0
    )
    assert values["llm_fact_accuracy"] < 1.0
    assert any(not r.passed for r in results)


def test_a_model_that_follows_an_injection_is_counted() -> None:
    jobs = build_jobs()
    good = perfect_extract(jobs)
    injected = {j.text: j.injected for j in jobs if j.injected}

    def obeys(text: str) -> GroundedJob:
        out = good(text)
        if text in injected:
            out.requirements.append({"text": "Obeyed", "kind": "required", "category": "other", "years_min": None,
                                     "quote": injected[text], "quote_start": 0, "quote_end": 0})  # fmt: skip
        return out

    metrics, results, _ = run_llm_extraction(jobs, obeys)
    values = {m.name: m.value for m in metrics}
    assert values["llm_injection_followed_rate"] == 1.0
    assert any("followed an injected instruction" in r.got for r in results)
    assert values["llm_requirement_precision"] < 1.0


def test_a_failing_provider_is_a_failed_case_not_a_crash() -> None:
    seen: list[str] = []

    def broken(text: str) -> GroundedJob:
        raise RuntimeError("busy")

    metrics, results, _ = run_llm_extraction(build_jobs()[:3], broken, failed=seen.append)
    assert len(seen) == 3 and all(not r.passed and r.got == "the call failed" for r in results)
    assert {m.name: m.value for m in metrics}["llm_requirement_recall"] == 0.0


# ------------------------------------------------------------------ the command


def test_the_command_exits_0_when_everything_holds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run"]) == 0
    assert "PASSED" in capsys.readouterr().out


def test_the_command_exits_1_when_a_metric_regresses(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from pv_domain.eligibility import EligibilityResult, EligibilityState

    monkeypatch.setattr(
        suites,
        "evaluate_eligibility",
        lambda f, p, y: EligibilityResult(EligibilityState.NOT_ELIGIBLE),
    )
    assert main(["run"]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_the_command_describes_the_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dataset"]) == 0
    out = capsys.readouterr().out
    assert "jobs-v1: 100 postings" in out and "injection: 14" in out


def test_the_llm_command_says_so_when_no_model_is_set(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from pv_config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    assert main(["run", "--llm"]) == 2
    assert "GEMINI_API_KEY and LLM_MODEL must be set" in capsys.readouterr().out
    get_settings.cache_clear()
