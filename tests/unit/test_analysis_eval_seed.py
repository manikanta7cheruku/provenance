"""Seed evaluation set for the evidence check (checkpoint 1.9).

Two small tables of cases that pin down behavior, so a change to the rules shows up as a failing row
instead of a vague feeling:

  VERDICT_CASES  what the agent may say about a requirement given the evidence it was shown, and what
                 code accepts. Each row is a mistake a model can make on a bad day.
  BAND_CASES     what the counts of verdicts mean for the recommendation band.

Every person, company and quote here is invented. What this set does NOT measure: whether a real model
finds the right evidence or writes a sensible verdict. That needs labeled real cases and arrives in
checkpoint 3.6, built from the "was this right?" answers people give from 1.9 onwards.
"""

from dataclasses import dataclass

import pytest

from pv_domain.analysis import (
    AcceptedVerdict,
    Band,
    Citation,
    ProposedVerdict,
    Rejected,
    Verdict,
    accept_verdict,
    score_analysis,
)

EVIDENCE = {
    "E1": (
        "c1",
        "Internship: Backend Intern at Lumen Works. Built 30 FastAPI endpoints for an internal tool",
    ),
    "E2": (
        "c2",
        "Education: B.E. in Computer Science at BMS College of Engineering, expected 2026",
    ),
    "E3": (
        "c3",
        "In my own words: I led a team of four students in the hackathon and we won second place",
    ),
    "E4": ("c4", "Skill: Python"),
}


@dataclass(frozen=True)
class VerdictCase:
    key: str
    proposal: ProposedVerdict
    expect: Verdict | str  # a verdict, or the rejection code


def p(verdict: str, kind: str | None, *cites: tuple[str, str]) -> ProposedVerdict:
    return ProposedVerdict(verdict, kind, tuple(Citation(a, b) for a, b in cites), "because")


VERDICT_CASES = [
    VerdictCase(
        "direct quote, met", p("met", "direct", ("E1", "Built 30 FastAPI endpoints")), Verdict.MET
    ),
    VerdictCase(
        "partial on a real quote", p("partial", "direct", ("E2", "expected 2026")), Verdict.PARTIAL
    ),
    VerdictCase(
        "answer cited as evidence",
        p("met", "direct", ("E3", "led a team of four students")),
        Verdict.MET,
    ),
    VerdictCase(
        "conflict is a valid verdict",
        p("conflicting", "direct", ("E2", "B.E. in Computer Science")),
        Verdict.CONFLICTING,
    ),
    VerdictCase("inferred cannot be met", p("met", "inferred", ("E4", "Python")), Verdict.PARTIAL),
    VerdictCase("not verified needs nothing", p("not_verified", None), Verdict.NOT_VERIFIED),
    VerdictCase(
        "invented number",
        p("met", "direct", ("E1", "Built 300 FastAPI endpoints")),
        "quote_not_found",
    ),
    VerdictCase(
        "invented employer",
        p("met", "direct", ("E1", "Senior Engineer at Google")),
        "quote_not_found",
    ),
    VerdictCase(
        "quote from the wrong entry",
        p("met", "direct", ("E2", "Built 30 FastAPI endpoints")),
        "quote_not_found",
    ),
    VerdictCase("label never shown", p("met", "direct", ("E9", "Python")), "unknown_evidence"),
    VerdictCase("no citation at all", p("met", "direct"), "evidence_required"),
    VerdictCase("kind missing", p("met", None, ("E4", "Python")), "evidence_kind_required"),
    VerdictCase(
        "a verdict that blames the person",
        p("lacks_skill", "direct", ("E4", "Python")),
        "unknown_verdict",
    ),
    VerdictCase(
        "one good and one invented quote",
        p("met", "direct", ("E4", "Python"), ("E1", "Ten years at Lumen")),
        "quote_not_found",
    ),
    VerdictCase(
        "casing and spacing differ",
        p("met", "direct", ("E1", "BUILT   30 fastapi ENDPOINTS")),
        Verdict.MET,
    ),
]


@pytest.mark.parametrize("case", VERDICT_CASES, ids=lambda c: c.key)
def test_verdict_acceptance(case: VerdictCase) -> None:
    got = accept_verdict(case.proposal, EVIDENCE)
    if isinstance(case.expect, Verdict):
        assert isinstance(got, AcceptedVerdict) and got.verdict is case.expect
    else:
        assert got == Rejected(case.expect)


def test_accepted_met_and_partial_always_carry_evidence_that_exists() -> None:
    known = {chunk_id for chunk_id, _ in EVIDENCE.values()}
    for case in VERDICT_CASES:
        got = accept_verdict(case.proposal, EVIDENCE)
        if isinstance(got, AcceptedVerdict) and got.verdict is not Verdict.NOT_VERIFIED:
            assert got.citations and all(c.chunk_id in known for c in got.citations)


@dataclass(frozen=True)
class BandCase:
    key: str
    required: tuple[int, int, int, int]  # met, partial, not verified, conflicting
    preferred: int
    eligible: bool
    band: Band


BAND_CASES = [
    BandCase("all met", (8, 0, 0, 0), 0, True, Band.STRONG),
    BandCase("four fifths is strong", (8, 0, 2, 0), 0, True, Band.STRONG),
    BandCase("partials count half", (4, 4, 2, 0), 0, True, Band.GOOD),
    BandCase("three fifths is good", (6, 0, 4, 0), 0, True, Band.GOOD),
    BandCase("half is a review", (5, 0, 5, 0), 0, True, Band.REVIEW),
    BandCase("a conflict caps at review", (9, 0, 0, 1), 0, True, Band.REVIEW),
    BandCase("little proof", (2, 0, 8, 0), 0, True, Band.NOT_RECOMMENDED),
    BandCase("nothing proven", (0, 0, 5, 0), 0, True, Band.NOT_RECOMMENDED),
    BandCase("nice to haves do not rescue", (1, 0, 9, 0), 5, True, Band.NOT_RECOMMENDED),
    BandCase("a failed gate beats everything", (10, 0, 0, 0), 3, False, Band.NOT_ELIGIBLE),
]


@pytest.mark.parametrize("case", BAND_CASES, ids=lambda c: c.key)
def test_band(case: BandCase) -> None:
    met, partial, missing, conflicting = case.required
    items = (
        [("required", "met")] * met
        + [("required", "partial")] * partial
        + [("required", "not_verified")] * missing
        + [("required", "conflicting")] * conflicting
        + [("preferred", "met")] * case.preferred
    )
    got = score_analysis(items, eligible=case.eligible, eligibility_note="Eligibility: ok.")
    assert got.band is case.band
    assert got.reasons and all(chr(0x2014) not in r for r in got.reasons)
