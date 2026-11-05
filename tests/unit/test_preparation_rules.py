"""Checkpoint 3.2: the rules of career preparation. Gap priority, difficulty, which preparation applies,
the plan, and feedback on a mock interview answer."""

from datetime import date

import pytest

from pv_domain.analysis import Verdict
from pv_domain.preparation import (
    ACTIONS,
    MAX_PLAN_DAYS,
    Priority,
    ReqRow,
    applicable_actions,
    build_concepts,
    clean_answer,
    coverage,
    difficulty_for,
    make_plan,
    mock_questions,
    prioritize,
    progress,
    role_family,
    score_answer,
    seniority_years,
)

TODAY = date(2026, 11, 5)


def row(
    i: int, text: str, kind: str, verdict: str, *, category: str = "skill", years: int | None = None
) -> ReqRow:
    return ReqRow(str(i), i, text, kind, category, years, verdict)


# ------------------------------------------------------------------ priority


@pytest.mark.parametrize(
    ("kind", "verdict", "expected"),
    [
        ("required", Verdict.NOT_VERIFIED, Priority.CRITICAL),
        ("required", Verdict.CONFLICTING, Priority.CRITICAL),
        ("required", "unchecked", Priority.CRITICAL),
        ("required", Verdict.PARTIAL, Priority.HIGH),
        ("required", Verdict.MET, Priority.OPTIONAL),
        ("preferred", Verdict.NOT_VERIFIED, Priority.USEFUL),
        ("preferred", Verdict.PARTIAL, Priority.USEFUL),
        ("preferred", Verdict.MET, Priority.OPTIONAL),
    ],
)
def test_the_priority_rule(kind: str, verdict: str, expected: Priority) -> None:
    assert prioritize(kind, verdict) is expected


def test_the_example_in_the_spec_ranks_aws_first_then_the_partial_ones() -> None:
    rows = [
        row(1, "Python", "required", Verdict.MET),
        row(2, "FastAPI", "required", Verdict.PARTIAL),
        row(3, "PostgreSQL", "required", Verdict.PARTIAL),
        row(4, "REST APIs", "required", Verdict.PARTIAL),
        row(5, "AWS", "required", Verdict.NOT_VERIFIED),
    ]
    concepts = build_concepts(rows, 3)
    assert [c.text for c in concepts][0] == "AWS"
    assert concepts[0].priority is Priority.CRITICAL
    assert [c.priority for c in concepts[1:4]] == [Priority.HIGH] * 3
    assert concepts[-1].text == "Python" and concepts[-1].priority is Priority.OPTIONAL


def test_gates_are_not_things_to_prepare() -> None:
    rows = [
        row(
            1,
            "Authorized to work in India",
            "required",
            Verdict.NOT_VERIFIED,
            category="work_authorization",
        ),
        row(2, "SQL", "required", Verdict.MET),
    ]
    assert [c.text for c in build_concepts(rows, 2)] == ["SQL"]
    assert coverage(rows)["required"] == 1


def test_every_concept_says_why() -> None:
    for concept in build_concepts([row(1, "Go", "required", Verdict.NOT_VERIFIED)], 2):
        assert concept.why and "profile" in concept.why


def test_coverage_counts_required_things_by_what_is_shown() -> None:
    rows = [
        row(1, "a", "required", Verdict.MET),
        row(2, "b", "required", Verdict.PARTIAL),
        row(3, "c", "required", Verdict.NOT_VERIFIED),
        row(4, "d", "required", Verdict.CONFLICTING),
        row(5, "e", "required", "unchecked"),
        row(6, "f", "preferred", Verdict.MET),
    ]
    assert coverage(rows) == {"required": 5, "met": 1, "partial": 1, "not_shown": 2, "unchecked": 1}


# ------------------------------------------------------------------ difficulty and seniority


def test_difficulty_follows_seniority_and_never_exceeds_it() -> None:
    assert difficulty_for(0, Priority.CRITICAL) == "medium"
    assert difficulty_for(0, Priority.HIGH) == "easy"
    assert difficulty_for(2, Priority.HIGH) == "medium"
    assert difficulty_for(2, Priority.CRITICAL) == "hard"
    assert difficulty_for(5, Priority.CRITICAL) == "expert"
    assert difficulty_for(5, Priority.OPTIONAL) == "medium"
    for years in range(0, 12):
        for priority in Priority:
            assert difficulty_for(years, priority) in {"easy", "medium", "hard", "expert"}
    assert (
        difficulty_for(1, Priority.CRITICAL) != "expert"
        and difficulty_for(3, Priority.CRITICAL) != "expert"
    )


def test_seniority_is_the_most_years_asked() -> None:
    rows = [
        row(1, "a", "required", Verdict.MET, years=2),
        row(2, "b", "required", Verdict.MET, years=5),
    ]
    assert seniority_years(rows) == 5
    assert seniority_years(rows, 7) == 7
    assert seniority_years([]) == 0


# ------------------------------------------------------------------ which preparation applies


def test_role_family_reads_the_title_first() -> None:
    assert role_family("Backend Engineer", []) == "software"
    assert role_family("Data Analyst", ["SQL", "Tableau"]) == "other"
    assert (
        role_family("Associate", ["Build backend services", "software engineer mindset"])
        == "software"
    )


def test_coding_and_system_design_only_for_software_roles_and_seniority() -> None:
    analyst = applicable_actions(
        family="other", years=1, title="Data Analyst", has_projects=False, has_evidence=True
    )
    assert "coding" not in analyst and "system_design" not in analyst
    junior = applicable_actions(
        family="software", years=1, title="Software Engineer", has_projects=True, has_evidence=True
    )
    assert "coding" in junior and "system_design" not in junior and "project_questions" in junior
    senior = applicable_actions(
        family="software",
        years=1,
        title="Senior Backend Engineer",
        has_projects=True,
        has_evidence=True,
    )
    assert "system_design" in senior
    experienced = applicable_actions(
        family="software", years=4, title="Engineer", has_projects=False, has_evidence=True
    )
    assert "system_design" in experienced and "project_questions" not in experienced


def test_without_evidence_there_are_no_questions_about_the_resume() -> None:
    keys = applicable_actions(
        family="other", years=0, title="Analyst", has_projects=False, has_evidence=False
    )
    assert "resume_questions" not in keys and "questions" in keys and "behavioral" in keys


def test_every_action_is_known_and_the_drafts_are_texts() -> None:
    keys = applicable_actions(
        family="software", years=5, title="Staff Engineer", has_projects=True, has_evidence=True
    )
    assert all(k in ACTIONS for k in keys)
    assert ACTIONS["outreach"].shape == "text" and ACTIONS["referral"].shape == "text"
    assert ACTIONS["questions"].shape == "list"


# ------------------------------------------------------------------ the plan


def concepts_for_plan() -> list:
    rows = [
        row(i, f"Topic {i}", "required", Verdict.NOT_VERIFIED if i < 3 else Verdict.PARTIAL)
        for i in range(1, 8)
    ]
    return build_concepts(rows, 3)


def test_no_date_or_a_past_date_gives_no_plan() -> None:
    assert make_plan(TODAY, None, concepts_for_plan()) == []
    assert make_plan(TODAY, date(2026, 11, 4), concepts_for_plan()) == []


def test_an_interview_today_is_a_review() -> None:
    plan = make_plan(TODAY, TODAY, concepts_for_plan())
    assert len(plan) == 1 and plan[0].kind == "review" and plan[0].day == TODAY


def test_the_plan_runs_to_the_interview_critical_first_and_ends_with_review_and_mock() -> None:
    plan = make_plan(TODAY, date(2026, 11, 12), concepts_for_plan())
    assert plan[0].day == TODAY and plan[-1].day == date(2026, 11, 12)
    assert [d.kind for d in plan[-2:]] == ["review", "mock"]
    assert [d.day for d in plan] == sorted(d.day for d in plan)
    first_topics = [t for d in plan for t in d.topics][:2]
    assert set(first_topics) == {"Topic 1", "Topic 2"}
    planned = {t for d in plan[:-2] for t in d.topics}
    assert len(planned) == 7


def test_a_far_date_is_capped() -> None:
    plan = make_plan(TODAY, date(2027, 6, 1), concepts_for_plan())
    assert len(plan) <= MAX_PLAN_DAYS


def test_progress_counts_what_is_ticked() -> None:
    assert progress({"a", "c"}, ["a", "b", "c", "d"]) == {"done": 2, "total": 4, "percent": 50}
    assert progress(set(), []) == {"done": 0, "total": 0, "percent": 0}
    assert progress({"zzz"}, ["a"])["done"] == 0


# ------------------------------------------------------------------ the mock interview


def test_mock_questions_start_with_the_most_important_and_treat_a_gap_as_a_gap() -> None:
    rows = [
        row(1, "Python", "required", Verdict.MET),
        row(2, "AWS", "required", Verdict.NOT_VERIFIED),
        row(3, "SQL", "required", Verdict.PARTIAL),
    ]
    questions = mock_questions(build_concepts(rows, 2))
    assert "AWS" in questions[0].text and "how would you approach learning it" in questions[0].text
    assert "where you are still building" in questions[1].text
    assert "Tell me about one time" in questions[2].text
    assert (
        len(
            mock_questions(
                build_concepts([row(i, f"T{i}", "required", Verdict.MET) for i in range(20)], 2)
            )
        )
        == 6
    )
    assert mock_questions([])[0].requirement_id is None


GOOD = (
    "At Kestrel Analytics our team was rebuilding a reporting job. I wrote the SQL joins over 1.2 million rows "
    "using pandas and PostgreSQL, and I reduced the nightly run from 40 minutes to 12. As a result the analysts "
    "had their numbers before they started work."
)
EVIDENCE = [
    "Data Intern at Kestrel Analytics. Wrote SQL joins over 1.2 million rows with pandas and PostgreSQL. Reduced the nightly run from 40 minutes to 12."
]


def fb(answer: str, requirement: str = "SQL and PostgreSQL experience", **kw):  # type: ignore[no-untyped-def]
    return score_answer(
        answer,
        requirement_text=requirement,
        evidence_texts=kw.get("evidence", EVIDENCE),
        job_words=["SQL", "PostgreSQL"],
        next_topic=kw.get("next"),
    )


def test_a_good_answer_scores_well_and_says_so() -> None:
    result = fb(GOOD)
    scores = {r.name: r.score for r in result.rubric}
    assert (
        scores["Structure"] == 3
        and scores["Specifics"] >= 2
        and scores["Relevance"] >= 2
        and scores["Honesty"] == 3
    )
    assert result.unsupported_claims == ()
    assert result.total >= 10 and result.maximum == 12


def test_a_thin_answer_is_told_what_to_add() -> None:
    result = fb("I know SQL.")
    notes = {r.name: r.note for r in result.rubric}
    assert "Too short" in notes["Structure"]
    assert "number" in notes["Specifics"]


def test_a_claim_not_in_the_profile_is_named() -> None:
    answer = (
        GOOD + " I also managed a team of 14 engineers at Google and shipped it with Kubernetes."
    )
    result = fb(answer)
    assert result.unsupported_claims
    joined = " ".join(result.unsupported_claims).lower()
    assert "14" in joined or "google" in joined or "kubernetes" in joined
    honesty = next(r for r in result.rubric if r.name == "Honesty")
    assert honesty.score < 3 and "not in your profile" in honesty.note


def test_a_long_answer_is_told_to_cut() -> None:
    result = fb(("I built a thing at work and it improved the result for the team. " * 40).strip())
    assert "Long" in next(r for r in result.rubric if r.name == "Structure").note


def test_an_answer_that_misses_the_point_is_told_to_use_the_postings_words() -> None:
    result = fb(
        "I enjoy working with people and I am a quick learner when the situation changes.",
        requirement="Kubernetes cluster operations",
    )
    assert next(r for r in result.rubric if r.name == "Relevance").score == 0


def test_the_follow_up_points_at_the_next_topic_or_says_you_are_done() -> None:
    assert "AWS" in fb(GOOD, next="AWS").follow_up
    assert "every topic" in fb(GOOD).follow_up


def test_answers_are_cleaned_and_capped() -> None:
    assert clean_answer("  a\r\n\r\n\r\n\r\nb  ") == "a\n\nb"
    assert len(clean_answer("x" * 9999)) == 3000
