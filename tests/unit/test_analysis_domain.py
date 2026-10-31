"""Verdict acceptance, confidence, scoring bands and the gap plan."""

import pytest

from pv_domain.analysis import (
    SCORING_VERSION,
    AnalysisUiState,
    Band,
    Citation,
    Confidence,
    ProposedVerdict,
    Rejected,
    Verdict,
    accept_verdict,
    analysis_ui_state,
    confidence_for,
    gap_plan,
    score_analysis,
    seed_query,
)

SEEN = {
    "E1": (
        "chunk-1",
        "Internship: Data Intern at Kestrel Analytics. Cleaned six CSV sources with pandas",
    ),
    "E2": ("chunk-2", "Skill: Python"),
}


def propose(
    verdict: str = "met", kind: str | None = "direct", *cites: tuple[str, str]
) -> ProposedVerdict:
    return ProposedVerdict(verdict, kind, tuple(Citation(a, b) for a, b in cites), "because")


class TestAcceptVerdict:
    def test_a_quote_found_in_the_cited_evidence_is_accepted(self) -> None:
        got = accept_verdict(
            propose("met", "direct", ("E1", "Cleaned six CSV sources with pandas")), SEEN
        )
        assert not isinstance(got, Rejected)
        assert got.verdict is Verdict.MET
        assert got.citations[0].chunk_id == "chunk-1" and not got.capped

    def test_case_and_spacing_may_differ_but_the_words_may_not(self) -> None:
        ok = accept_verdict(propose("met", "direct", ("E1", "CLEANED   six csv sources")), SEEN)
        bad = accept_verdict(propose("met", "direct", ("E1", "built a data warehouse")), SEEN)
        assert not isinstance(ok, Rejected)
        assert bad == Rejected("quote_not_found")

    def test_evidence_that_was_not_shown_cannot_be_cited(self) -> None:
        assert accept_verdict(propose("met", "direct", ("E9", "Skill: Python")), SEEN) == Rejected(
            "unknown_evidence"
        )

    def test_met_partial_and_conflicting_need_a_citation(self) -> None:
        for verdict in ("met", "partial", "conflicting"):
            assert accept_verdict(propose(verdict, "direct"), SEEN) == Rejected("evidence_required")

    def test_the_kind_of_evidence_is_required(self) -> None:
        assert accept_verdict(propose("met", None, ("E2", "Python")), SEEN) == Rejected(
            "evidence_kind_required"
        )

    def test_inferred_evidence_can_never_make_a_requirement_met(self) -> None:
        got = accept_verdict(propose("met", "inferred", ("E2", "Python")), SEEN)
        assert not isinstance(got, Rejected)
        assert got.verdict is Verdict.PARTIAL and got.capped

    def test_not_verified_needs_no_evidence(self) -> None:
        got = accept_verdict(propose("not_verified", None), SEEN)
        assert not isinstance(got, Rejected) and got.verdict is Verdict.NOT_VERIFIED

    def test_an_unknown_verdict_is_rejected(self) -> None:
        assert accept_verdict(propose("lacks_skill", "direct", ("E2", "Python")), SEEN) == Rejected(
            "unknown_verdict"
        )

    def test_one_bad_citation_rejects_the_verdict(self) -> None:
        got = accept_verdict(
            propose("met", "direct", ("E2", "Python"), ("E1", "invented words")), SEEN
        )
        assert got == Rejected("quote_not_found")

    def test_the_reason_is_trimmed(self) -> None:
        long = ProposedVerdict("not_verified", None, (), "word " * 200)
        got = accept_verdict(long, SEEN)
        assert not isinstance(got, Rejected) and len(got.reason) <= 300


def test_confidence_comes_from_the_evidence_not_the_model() -> None:
    assert confidence_for("met", "direct") is Confidence.HIGH
    assert confidence_for("partial", "direct") is Confidence.MEDIUM
    assert confidence_for("met", "inferred") is Confidence.MEDIUM
    assert confidence_for("not_verified", None) is Confidence.NONE


def items(
    met: int = 0, partial: int = 0, nv: int = 0, conflict: int = 0, pref: list[str] | None = None
):
    rows = [("required", Verdict.MET.value)] * met
    rows += [("required", Verdict.PARTIAL.value)] * partial
    rows += [("required", Verdict.NOT_VERIFIED.value)] * nv
    rows += [("required", Verdict.CONFLICTING.value)] * conflict
    rows += [("preferred", v) for v in (pref or [])]
    return rows


class TestScoring:
    @pytest.mark.parametrize(
        ("met", "partial", "nv", "band"),
        [
            (10, 0, 0, Band.STRONG),
            (8, 0, 2, Band.STRONG),  # exactly four fifths
            (7, 0, 3, Band.GOOD),
            (6, 0, 4, Band.GOOD),  # exactly three fifths
            (5, 0, 5, Band.REVIEW),
            (2, 3, 5, Band.REVIEW),  # 3.5 of 10 is exactly the review line
            (3, 0, 7, Band.NOT_RECOMMENDED),
            (0, 0, 4, Band.NOT_RECOMMENDED),
        ],
    )
    def test_bands_follow_the_thresholds(self, met: int, partial: int, nv: int, band: Band) -> None:
        got = score_analysis(
            items(met, partial, nv), eligible=True, eligibility_note="Eligibility: ok."
        )
        assert got.band is band and got.scoring_version == SCORING_VERSION

    def test_a_conflict_caps_the_band_at_review(self) -> None:
        got = score_analysis(items(met=9, conflict=1), eligible=True, eligibility_note="x")
        assert got.band is Band.REVIEW
        assert any("disagrees" in r for r in got.reasons)

    def test_a_failed_gate_means_not_eligible_and_no_coverage_story(self) -> None:
        got = score_analysis(
            items(met=10), eligible=False, eligibility_note="Eligibility: no visa."
        )
        assert got.band is Band.NOT_ELIGIBLE
        assert got.reasons[0] == "Eligibility: no visa."
        assert not any("supported" in r for r in got.reasons)

    def test_nice_to_haves_never_change_the_band(self) -> None:
        base = score_analysis(items(met=6, nv=4), eligible=True, eligibility_note="x")
        more = score_analysis(
            items(met=6, nv=4, pref=["met", "met", "met"]), eligible=True, eligibility_note="x"
        )
        assert base.band is more.band is Band.GOOD
        assert more.preferred_supported == 3

    def test_not_verified_is_explained_as_missing_proof(self) -> None:
        got = score_analysis(items(met=1, nv=1), eligible=True, eligibility_note="x")
        assert any("no proof was found, not that you lack the skill" in r for r in got.reasons)

    def test_counts_add_up_and_use_plain_wording(self) -> None:
        got = score_analysis(items(met=2, partial=1, nv=1), eligible=True, eligibility_note="x")
        assert (got.met, got.partial, got.not_verified, got.supported) == (2, 1, 1, 3)
        assert "3 of 4 required requirements supported (2 fully, 1 partly)." in got.reasons[0]
        assert all(chr(0x2014) not in r for r in got.reasons)

    def test_no_required_items_does_not_divide_by_zero(self) -> None:
        got = score_analysis([("preferred", "met")], eligible=True, eligibility_note="x")
        assert got.required_total == 0 and got.band in (Band.REVIEW, Band.NOT_RECOMMENDED)
        empty = score_analysis([], eligible=True, eligibility_note="x")
        assert empty.band is Band.REVIEW


class TestGapPlan:
    def test_only_required_items_that_are_not_met_appear(self) -> None:
        rows = [
            ("1", "SQL", "required", "skill", "met"),
            ("2", "Kubernetes", "required", "skill", "not_verified"),
            ("3", "2 years", "required", "experience", "partial"),
            ("4", "Tableau", "preferred", "skill", "not_verified"),
            ("5", "BE degree", "required", "education", "conflicting"),
        ]
        gaps = gap_plan(rows)
        assert [g.requirement_id for g in gaps] == ["2", "3", "5"]
        assert gaps[1].next_step.startswith("What you have covers part of it.")
        assert "disagree" in gaps[2].next_step

    def test_an_unknown_category_still_gets_a_plan(self) -> None:
        gap = gap_plan([("1", "Odd", "required", "mystery", "not_verified")])[0]
        assert gap.proof_needed and gap.next_step


def test_ui_state_mapping() -> None:
    assert analysis_ui_state(None) is AnalysisUiState.NOT_STARTED
    assert analysis_ui_state("queued") is AnalysisUiState.WORKING
    assert analysis_ui_state("analyzing") is AnalysisUiState.WORKING
    assert analysis_ui_state("needs_user_input") is AnalysisUiState.NEEDS_ANSWER
    assert analysis_ui_state("complete") is AnalysisUiState.READY
    assert analysis_ui_state("failed") is AnalysisUiState.FAILED


class TestSeedQuery:
    def test_key_words_are_kept_and_any_of_them_may_match(self) -> None:
        assert seed_query("Write SQL to answer product questions") == (
            "write OR sql OR answer OR product OR questions"
        )

    def test_filler_words_are_dropped(self) -> None:
        assert seed_query("Strong experience with Python and pandas") == "python OR pandas"

    def test_single_letter_languages_survive_and_duplicates_do_not(self) -> None:
        assert seed_query("C++ and R, R, R") == "c++ OR r"

    def test_it_is_bounded_and_can_be_empty(self) -> None:
        assert seed_query(" ".join(f"word{i}" for i in range(40))).count(" OR ") == 9
        assert seed_query("the and of") == ""
