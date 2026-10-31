"""Verdicts, scoring and the gap plan for one job. Pure rules, no database, no model.

The evidence agent (pv_llm.evidence_agent) proposes a verdict for each requirement. This module
decides what is accepted and what the result means:

  accept_verdict   a Met, Partial or Conflicting verdict must cite evidence that the agent really
                   saw in this run, with words found in that evidence. Otherwise it is rejected.
                   Evidence that is only inferred can never reach Met.
  score_analysis   coverage of what the posting requires, turned into a band by fixed thresholds.
                   Versioned. Every band comes with plain reasons. A failed hard gate is
                   "not eligible" and has no score at all.
  gap_plan         for each required item that is not fully supported, what would count as proof.

Absence of evidence is "not verified", never "the candidate lacks this skill".
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from pv_domain.job import find_quote

SCORING_VERSION = "scoring-1"

# Agent limits. The agent stops at the first one it reaches and the requirement stays unverified.
MAX_STEPS_PER_REQUIREMENT = 4  # model calls
MAX_TOOL_CALLS_PER_REQUIREMENT = 3
MAX_MODEL_CALLS_PER_RUN = 90
MAX_QUESTIONS_PER_RUN = 3
MAX_CITATIONS = 3
MAX_ANSWER_CHARS = 1000
MAX_QUESTION_CHARS = 300
MAX_REASON_CHARS = 300

# Requirements in these categories are decided by the eligibility gates, not by evidence.
GATE_CATEGORIES = frozenset({"work_authorization", "location"})

# Coverage thresholds for the bands. Fractions of the required items that are supported,
# counting Met as 1 and Partial as one half.
STRONG_COVERAGE = 0.8
GOOD_COVERAGE = 0.6
REVIEW_COVERAGE = 0.35


class Verdict(StrEnum):
    MET = "met"
    PARTIAL = "partial"
    NOT_VERIFIED = "not_verified"
    CONFLICTING = "conflicting"


class EvidenceKind(StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NONE = "none"


class Band(StrEnum):
    STRONG = "strong"
    GOOD = "good"
    REVIEW = "review"
    NOT_RECOMMENDED = "not_recommended"
    NOT_ELIGIBLE = "not_eligible"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    NEEDS_USER_INPUT = "needs_user_input"
    COMPLETE = "complete"
    FAILED = "failed"


# What the person sees for the evidence check on a job.
class AnalysisUiState(StrEnum):
    NOT_STARTED = "not_started"
    WORKING = "working"
    NEEDS_ANSWER = "needs_answer"
    READY = "ready"
    FAILED = "failed"


class QuestionStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class AnalysisErrorCode(StrEnum):
    AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"


ANALYSIS_ERROR_MESSAGES = {
    AnalysisErrorCode.AI_NOT_CONFIGURED.value: (
        "The checking service is not set up yet. Your results so far are saved. Try again later."
    ),
    AnalysisErrorCode.AI_UNAVAILABLE.value: (
        "The checking service did not answer. Your results so far are saved. "
        "Check again in a few minutes and it continues where it stopped."
    ),
}

# Why a requirement is not verified, in words for the person.
REASON_MESSAGES = {
    "no_evidence": "Nothing in your profile supports this yet.",
    "rejected": "The reader named evidence that could not be confirmed in your profile.",
    "budget_spent": "The search limit was reached before enough evidence was found.",
    "user_skipped": "You chose not to answer, so this stays unverified.",
}


def analysis_ui_state(status: str | None) -> AnalysisUiState:
    if status is None:
        return AnalysisUiState.NOT_STARTED
    if status == AnalysisStatus.NEEDS_USER_INPUT:
        return AnalysisUiState.NEEDS_ANSWER
    if status == AnalysisStatus.COMPLETE:
        return AnalysisUiState.READY
    if status == AnalysisStatus.FAILED:
        return AnalysisUiState.FAILED
    return AnalysisUiState.WORKING


@dataclass(frozen=True)
class Citation:
    """The agent's claim that these words, found in this piece of evidence, support a verdict."""

    label: str  # the short name the agent was given for the evidence, such as "E2"
    quote: str


@dataclass(frozen=True)
class ProposedVerdict:
    verdict: str
    evidence_kind: str | None
    citations: tuple[Citation, ...]
    reason: str


@dataclass(frozen=True)
class AcceptedCitation:
    chunk_id: str
    quote: str


@dataclass(frozen=True)
class AcceptedVerdict:
    verdict: Verdict
    evidence_kind: EvidenceKind | None
    citations: tuple[AcceptedCitation, ...]
    reason: str
    capped: bool  # Met was lowered to Partial because the evidence was only inferred


@dataclass(frozen=True)
class Rejected:
    code: str  # a short word the agent is told, never a quote of anyone's text


_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.]*")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "or",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "at",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "you",
        "your",
        "we",
        "our",
        "their",
        "it",
        "its",
        "can",
        "will",
        "must",
        "should",
        "strong",
        "good",
        "excellent",
        "solid",
        "basic",
        "understanding",
        "knowledge",
        "experience",
        "experienced",
        "ability",
        "able",
        "including",
        "such",
        "like",
        "etc",
        "work",
        "working",
        "use",
        "using",
        "used",
        "have",
        "has",
        "had",
        "having",
        "years",
        "year",
        "plus",
        "least",
        "more",
        "than",
        "into",
        "through",
        "across",
        "about",
        "per",
        "via",
    ]
)


def seed_query(requirement: str, limit: int = 10) -> str:
    """Search words for a requirement, joined with OR.

    Keyword search needs every word of a plain query to appear in one entry, so a whole sentence
    finds nothing. The words that matter are kept and any one of them may match. Ranking then puts
    entries that match several of them first, and meaning search covers paraphrase.
    """
    seen: list[str] = []
    for word in _WORD.findall(requirement):
        word = word.strip(".")
        low = word.lower()
        if low in _STOPWORDS or (len(word) < 2 and low not in ("c", "r")) or low in seen:
            continue
        seen.append(low)
    return " OR ".join(seen[:limit])


def clean_reason(text: str) -> str:
    return " ".join(text.split())[:MAX_REASON_CHARS]


def accept_verdict(
    proposed: ProposedVerdict, seen: Mapping[str, tuple[str, str]]
) -> AcceptedVerdict | Rejected:
    """Check a proposed verdict against the evidence the agent saw in this run.

    `seen` maps the agent's short label to (chunk id, chunk text). Only those labels exist, so a
    citation of anything else, or of another person's evidence, cannot be accepted.
    """
    try:
        verdict = Verdict(proposed.verdict)
    except ValueError:
        return Rejected("unknown_verdict")
    reason = clean_reason(proposed.reason)
    if verdict is Verdict.NOT_VERIFIED:
        return AcceptedVerdict(verdict, None, (), reason, capped=False)
    try:
        kind = EvidenceKind(proposed.evidence_kind or "")
    except ValueError:
        return Rejected("evidence_kind_required")
    accepted: list[AcceptedCitation] = []
    for citation in proposed.citations[:MAX_CITATIONS]:
        entry = seen.get(citation.label)
        if entry is None:
            return Rejected("unknown_evidence")
        chunk_id, text = entry
        if find_quote(text, citation.quote) is None:
            return Rejected("quote_not_found")
        accepted.append(AcceptedCitation(chunk_id, citation.quote.strip()))
    if not accepted:
        return Rejected("evidence_required")
    capped = verdict is Verdict.MET and kind is EvidenceKind.INFERRED
    if capped:
        verdict = Verdict.PARTIAL
    return AcceptedVerdict(verdict, kind, tuple(accepted), reason, capped)


def confidence_for(verdict: str, evidence_kind: str | None) -> Confidence:
    """Confidence comes from the evidence, never from how sure the model sounded."""
    if verdict == Verdict.MET and evidence_kind == EvidenceKind.DIRECT:
        return Confidence.HIGH
    if verdict in (Verdict.MET, Verdict.PARTIAL, Verdict.CONFLICTING):
        return Confidence.MEDIUM
    return Confidence.NONE


@dataclass(frozen=True)
class ScoreResult:
    scoring_version: str
    band: Band
    required_total: int
    met: int
    partial: int
    conflicting: int
    not_verified: int
    preferred_total: int
    preferred_supported: int
    reasons: tuple[str, ...]

    @property
    def supported(self) -> int:
        return self.met + self.partial


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def score_analysis(
    items: Sequence[tuple[str, str]], *, eligible: bool, eligibility_note: str
) -> ScoreResult:
    """Items are (kind, verdict) for each evidence-checked requirement. `kind` is required or
    preferred. A requirement with no verdict yet counts as not verified."""
    required = [v for k, v in items if k == "required"]
    preferred = [v for k, v in items if k == "preferred"]
    met = required.count(Verdict.MET)
    partial = required.count(Verdict.PARTIAL)
    conflicting = required.count(Verdict.CONFLICTING)
    not_verified = len(required) - met - partial - conflicting
    pref_supported = sum(1 for v in preferred if v in (Verdict.MET, Verdict.PARTIAL))

    reasons: list[str] = []
    if not eligible:
        band = Band.NOT_ELIGIBLE
        reasons.append(eligibility_note)
        reasons.append("No score is shown while a hard requirement is not met.")
    else:
        if required:
            coverage = (met + 0.5 * partial) / len(required)
            band = _band(coverage, conflicting)
            reasons.append(
                f"{met + partial} of {_plural(len(required), 'required requirement', 'required requirements')} "
                f"supported ({met} fully, {partial} partly)."
            )
        elif preferred:
            coverage = pref_supported / len(preferred)
            band = Band.REVIEW if coverage >= GOOD_COVERAGE else Band.NOT_RECOMMENDED
            reasons.append(
                "The posting lists nothing it strictly requires, so only the nice-to-haves count."
            )
        else:
            band = Band.REVIEW
            reasons.append("There was nothing to check against your evidence.")
        if not_verified:
            reasons.append(
                f"{_plural(not_verified, 'requirement is', 'requirements are')} not verified. "
                "That means no proof was found, not that you lack the skill. Adding evidence can change it."
            )
        if conflicting:
            reasons.append(
                f"Your evidence disagrees with {_plural(conflicting, 'requirement', 'requirements')}. "
                "A band cannot be Strong or Good while that is unresolved."
            )
        if preferred:
            reasons.append(
                f"Nice to have: {pref_supported} of {len(preferred)} supported. "
                "These never lower the band."
            )
        reasons.append(eligibility_note)
    return ScoreResult(
        scoring_version=SCORING_VERSION,
        band=band,
        required_total=len(required),
        met=met,
        partial=partial,
        conflicting=conflicting,
        not_verified=not_verified,
        preferred_total=len(preferred),
        preferred_supported=pref_supported,
        reasons=tuple(reasons),
    )


def _band(coverage: float, conflicting: int) -> Band:
    if coverage >= STRONG_COVERAGE and conflicting == 0:
        return Band.STRONG
    if coverage >= GOOD_COVERAGE and conflicting == 0:
        return Band.GOOD
    if coverage >= REVIEW_COVERAGE:
        return Band.REVIEW
    return Band.NOT_RECOMMENDED


@dataclass(frozen=True)
class Gap:
    requirement_id: str
    requirement: str
    state: str  # the verdict this gap comes from
    proof_needed: str
    next_step: str


_PROOF = {
    "skill": (
        "An entry that shows you using it: a project, a job or an internship that names it.",
        "Add a project or experience entry that says what you built with it. If it is learned but not "
        "yet used, build one small project and add it.",
    ),
    "experience": (
        "Dates and duties for the work, so the length of time can be checked.",
        "Add the start and end dates and what you did to the matching experience entry.",
    ),
    "education": (
        "An education entry with the degree or course and when it ended or will end.",
        "Add or correct the education entry. If you are still studying, give the expected end date.",
    ),
    "certification": (
        "A certification entry with its name and who issued it.",
        "Add the certificate if you hold it. If not, this is a concrete thing to earn.",
    ),
    "language": (
        "A language entry or a line in an entry showing you used it at work or study.",
        "Add the language and your level, or an entry where you used it.",
    ),
    "other": (
        "A profile entry or your own written answer that speaks to it directly.",
        "Answer the question on this page, or add an entry that covers it.",
    ),
}


def gap_plan(rows: Sequence[tuple[str, str, str, str, str]]) -> list[Gap]:
    """Rows are (requirement id, text, kind, category, verdict). Only required items that are not
    fully supported appear. Everything here is a fixed template: nothing is invented."""
    gaps: list[Gap] = []
    for req_id, text, kind, category, verdict in rows:
        if kind != "required" or verdict == Verdict.MET:
            continue
        proof, step = _PROOF.get(category, _PROOF["other"])
        if verdict == Verdict.CONFLICTING:
            step = (
                "Your entries disagree about this. Fix the entry that is wrong, then check again."
            )
        elif verdict == Verdict.PARTIAL:
            step = "What you have covers part of it. " + step
        gaps.append(Gap(req_id, text, verdict, proof, step))
    return gaps
