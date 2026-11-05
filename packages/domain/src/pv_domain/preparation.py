"""Career preparation, as rules.

The question this answers: given this job and what the person's profile can prove, what should they
prepare next, and why? It is built on what already exists (the job's requirements and the evidence
check) and it adds no new agent (ADR-0017). Code owns the order of things. A model is asked only for
wording, and every claim it makes about the person is checked against their evidence afterwards.

What is decided here, with no model:

  - **Gap analysis and priority.** A required requirement the profile cannot show is a Critical gap,
    a partly shown one is High priority, a preferred one that is not met is Useful, anything else is
    Optional. The rules are versioned (`RULES_VERSION`) so a change is visible.
  - **Difficulty.** From the seniority the posting asks for and how important the topic is. Never
    higher than the job supports.
  - **Which preparation applies.** Coding and system design only appear for software roles, system
    design only for a role that asks for some seniority, project questions only when the profile has
    projects.
  - **The plan.** From today to the interview date, critical topics first, a review and a mock
    interview at the end.
  - **Progress.** Counted from what the person has ticked.
  - **Mock interview feedback.** A rubric computed from the answer itself: structure, specificity,
    relevance to the requirement and honesty (claims not in the person's evidence are named).

Wording is hedged on purpose: "Likely question", "High-priority preparation area". Nothing says a
question will be asked, and nothing invents an interview process or what employees said.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from pv_domain.analysis import GATE_CATEGORIES, Verdict
from pv_domain.tailoring import verify_text

RULES_VERSION = "prep-rules-1"
MAX_PLAN_DAYS = 28
MAX_ITEMS_PER_OUTPUT = 12
MAX_ANSWER_CHARS = 3000
MIN_ANSWER_CHARS = 20


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    USEFUL = "useful"
    OPTIONAL = "optional"


PRIORITY_ORDER = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.USEFUL: 2, Priority.OPTIONAL: 3}
PRIORITY_LABELS = {
    Priority.CRITICAL: "Critical gap",
    Priority.HIGH: "High-priority preparation area",
    Priority.USEFUL: "Useful to prepare",
    Priority.OPTIONAL: "Optional",
}

LIKELY_LABEL = (
    "Likely questions, based on this job description. They are preparation, not a prediction of "
    "what will be asked."
)
INSUFFICIENT_EVIDENCE = (
    "Your profile does not currently contain enough evidence to answer this confidently. Add what "
    "you have done, or use this to decide what to learn."
)
GENERATED_LABEL = (
    "Written for you from your own evidence. Check every line. Anything it says about you that is "
    "not in your evidence is listed beside it."
)


# ---------------------------------------------------------------- gaps and priorities


@dataclass(frozen=True)
class ReqRow:
    """What preparation needs to know about one requirement."""

    requirement_id: str
    ordinal: int
    text: str
    kind: str  # "required" or "preferred"
    category: str
    years_min: int | None
    verdict: str  # a Verdict, or "unchecked" when the evidence check has not run


@dataclass(frozen=True)
class Concept:
    requirement_id: str
    text: str
    kind: str
    category: str
    verdict: str
    priority: Priority
    difficulty: str
    why: str


def prioritize(kind: str, verdict: str) -> Priority:
    """The rule. Critical when a required thing cannot be shown, High when it is only partly shown,
    Useful when a preferred thing is not met, Optional otherwise."""
    shown = verdict == Verdict.MET
    if kind == "required":
        if verdict in (Verdict.NOT_VERIFIED, Verdict.CONFLICTING, "unchecked"):
            return Priority.CRITICAL
        if verdict == Verdict.PARTIAL:
            return Priority.HIGH
        return Priority.OPTIONAL
    return Priority.OPTIONAL if shown else Priority.USEFUL


_WHY = {
    Priority.CRITICAL: "The job requires it and your profile does not show it yet.",
    Priority.HIGH: "The job requires it and your profile shows only part of it.",
    Priority.USEFUL: "The job prefers it and your profile does not show it.",
    Priority.OPTIONAL: "Your profile already supports it, or it is a small extra.",
}


def seniority_years(rows: Sequence[ReqRow], min_years_fact: int | None = None) -> int:
    """The most years of experience the posting asks for, from its requirements or its facts."""
    asked = [r.years_min for r in rows if r.years_min is not None]
    if min_years_fact is not None:
        asked.append(min_years_fact)
    return max(asked, default=0)


def difficulty_for(years: int, priority: Priority) -> str:
    """Easy, medium, hard or expert, never beyond what the seniority supports."""
    base = 0 if years <= 1 else 1 if years <= 3 else 2 if years <= 6 else 3
    if priority is Priority.CRITICAL:
        base += 1
    elif priority is Priority.OPTIONAL:
        base -= 1
    cap = 1 if years <= 1 else 2 if years <= 3 else 3
    return ("easy", "medium", "hard", "expert")[max(0, min(base, cap))]


def build_concepts(rows: Sequence[ReqRow], years: int) -> list[Concept]:
    concepts = []
    for row in rows:
        if row.category in GATE_CATEGORIES:
            continue
        priority = prioritize(row.kind, row.verdict)
        concepts.append(
            Concept(
                requirement_id=row.requirement_id,
                text=row.text,
                kind=row.kind,
                category=row.category,
                verdict=row.verdict,
                priority=priority,
                difficulty=difficulty_for(years, priority),
                why=_WHY[priority],
            )
        )
    return sorted(concepts, key=lambda c: (PRIORITY_ORDER[c.priority], c.text.lower()))


def coverage(rows: Sequence[ReqRow]) -> dict[str, int]:
    """Counts of required requirements by what the evidence shows."""
    required = [r for r in rows if r.kind == "required" and r.category not in GATE_CATEGORIES]
    return {
        "required": len(required),
        "met": sum(1 for r in required if r.verdict == Verdict.MET),
        "partial": sum(1 for r in required if r.verdict == Verdict.PARTIAL),
        "not_shown": sum(
            1 for r in required if r.verdict in (Verdict.NOT_VERIFIED, Verdict.CONFLICTING)
        ),
        "unchecked": sum(1 for r in required if r.verdict == "unchecked"),
    }


# ---------------------------------------------------------------- which preparation applies

_SOFTWARE = re.compile(
    r"\b(software|developer|engineer|backend|back-end|frontend|front-end|full[- ]?stack|devops|sre|"
    r"programmer|mobile|android|ios|data engineer|machine learning engineer|platform)\b",
    re.I,
)
_SENIOR = re.compile(r"\b(senior|sr\.?|lead|staff|principal|architect|manager)\b", re.I)


def role_family(title: str, requirement_texts: Iterable[str]) -> str:
    """ "software" for a role that writes software, else "other". Looks at the title first."""
    if _SOFTWARE.search(title or ""):
        return "software"
    joined = " ".join(requirement_texts)
    return "software" if len(_SOFTWARE.findall(joined)) >= 2 else "other"


@dataclass(frozen=True)
class ActionSpec:
    key: str
    label: str
    description: str
    # "list" gives a set of items (questions, topics). "text" gives one draft the person edits.
    shape: str


ACTIONS: dict[str, ActionSpec] = {
    a.key: a
    for a in (
        ActionSpec(
            "questions",
            "Interview questions",
            "Likely questions grouped by theme and difficulty, each tied to a requirement, with guidance built from your own evidence.",
            "list",
        ),
        ActionSpec(
            "resume_questions",
            "Questions about your resume",
            "The claims and tools in your profile an interviewer is likely to ask you to go deeper on.",
            "list",
        ),
        ActionSpec(
            "project_questions",
            "Questions about your projects",
            "Deeper questions about the projects in your profile.",
            "list",
        ),
        ActionSpec(
            "behavioral",
            "Behavioral prompts",
            "Situation, task, action and result prompts, each pointing at something you have really done.",
            "list",
        ),
        ActionSpec(
            "technical",
            "Technical concepts",
            "The concepts this role is likely to test, explained briefly, with what you can already point to.",
            "list",
        ),
        ActionSpec(
            "coding",
            "Coding and data structures",
            "Topics and patterns to practise, ordered by what the job asks for and where you are thin.",
            "list",
        ),
        ActionSpec(
            "system_design",
            "System design",
            "Design topics suited to the seniority the job asks for.",
            "list",
        ),
        ActionSpec(
            "outreach",
            "Outreach message",
            "A short message to someone at the company, in your voice. You send it.",
            "text",
        ),
        ActionSpec(
            "referral",
            "Referral request",
            "A short message asking someone you know for a referral. You send it.",
            "text",
        ),
    )
}


def applicable_actions(
    *, family: str, years: int, title: str, has_projects: bool, has_evidence: bool
) -> list[str]:
    """The preparation that makes sense for this job and this person, in the order shown."""
    keys = ["questions"]
    if has_evidence:
        keys.append("resume_questions")
    if has_projects:
        keys.append("project_questions")
    keys += ["behavioral", "technical"]
    if family == "software":
        keys.append("coding")
        if years >= 3 or _SENIOR.search(title or ""):
            keys.append("system_design")
    keys += ["outreach", "referral"]
    return keys


# ---------------------------------------------------------------- the plan


@dataclass(frozen=True)
class PlanDay:
    day: date
    kind: str  # "learn", "practise", "review" or "mock"
    topics: tuple[str, ...]


def make_plan(today: date, interview: date | None, concepts: Sequence[Concept]) -> list[PlanDay]:
    """A day by day roadmap to the interview. Critical topics come first and the last two days are
    for review and a mock interview. No date, or a date that has passed, gives no plan."""
    if interview is None or interview < today:
        return []
    days = min((interview - today).days + 1, MAX_PLAN_DAYS)
    topics = [c.text for c in concepts if c.priority is not Priority.OPTIONAL]
    if days == 1:
        return [PlanDay(today, "review", tuple(topics[:3]))]
    study_days = max(1, days - 2)
    plan: list[PlanDay] = []
    per_day = max(1, -(-len(topics) // study_days)) if topics else 0
    for index in range(study_days):
        chunk = tuple(topics[index * per_day : (index + 1) * per_day]) if per_day else ()
        kind = "learn" if index < max(1, study_days // 2) else "practise"
        plan.append(PlanDay(today + timedelta(days=index), kind, chunk))
    plan.append(PlanDay(today + timedelta(days=study_days), "review", tuple(topics[:3])))
    plan.append(PlanDay(today + timedelta(days=study_days + 1), "mock", ()))
    return plan


def progress(done: set[str], keys: Sequence[str]) -> dict[str, int]:
    total = len(keys)
    finished = sum(1 for k in keys if k in done)
    return {
        "done": finished,
        "total": total,
        "percent": round(100 * finished / total) if total else 0,
    }


# ---------------------------------------------------------------- the mock interview


@dataclass(frozen=True)
class MockQuestion:
    requirement_id: str | None
    text: str
    priority: Priority


def mock_questions(concepts: Sequence[Concept], limit: int = 6) -> list[MockQuestion]:
    """Questions for a mock interview, most important first. A gap is asked as a gap: how would you
    approach it. Nothing is asked about something the profile cannot support as if it were known."""
    out: list[MockQuestion] = []
    for c in concepts:
        if len(out) >= limit:
            break
        if c.verdict == Verdict.MET:
            text = (
                f'The posting asks for: "{c.text}". Tell me about one time you did this. '
                "Say what the situation was, what you did and what changed."
            )
        elif c.verdict == Verdict.PARTIAL:
            text = (
                f'The posting asks for: "{c.text}". Tell me what you have done toward this and '
                "where you are still building."
            )
        else:
            text = (
                f'The posting asks for: "{c.text}". If you were asked about this, how would you '
                "approach learning it, and what related work could you point to?"
            )
        out.append(MockQuestion(c.requirement_id, text, c.priority))
    if not out:
        out.append(
            MockQuestion(
                None,
                "Tell me about a piece of work you are proud of. Say what the situation was, what "
                "you did and what changed.",
                Priority.OPTIONAL,
            )
        )
    return out


_ACTION = re.compile(
    r"\b(i (built|wrote|led|designed|fixed|ran|created|analy[sz]ed|improved|reduced|increased|"
    r"launched|delivered|owned|presented|tested|deployed|automated|migrated|learned|decided))\b",
    re.I,
)
_RESULT = re.compile(
    r"\b(result|resulted|so that|which (meant|led)|as a result|improved|reduced|increased|saved|"
    r"cut|grew|delivered|shipped|learned|outcome)\b",
    re.I,
)
_SITUATION = re.compile(
    r"\b(when|while|during|at |in my|for a|for the|our team|the (problem|goal|task|project))\b",
    re.I,
)
_NUMBER = re.compile(r"\b\d[\d,.]*%?\b")
_WORD = re.compile(r"[a-z][a-z+#.\-]{2,}", re.I)
_STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "was",
        "were",
        "are",
        "you",
        "your",
        "have",
        "has",
        "had",
        "will",
        "can",
        "not",
        "but",
        "all",
        "any",
        "into",
        "over",
        "about",
        "when",
        "what",
        "who",
        "how",
        "their",
        "they",
        "them",
        "than",
        "then",
        "also",
        "use",
        "used",
        "using",
        "work",
        "works",
        "worked",
        "experience",
        "years",
        "year",
        "strong",
        "good",
        "great",
        "ability",
        "able",
    ]
)


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP}


@dataclass(frozen=True)
class Rubric:
    name: str
    score: int  # 0 to 3
    note: str


@dataclass(frozen=True)
class Feedback:
    rubric: tuple[Rubric, ...]
    unsupported_claims: tuple[str, ...]
    words: int
    follow_up: str

    @property
    def total(self) -> int:
        return sum(r.score for r in self.rubric)

    @property
    def maximum(self) -> int:
        return 3 * len(self.rubric)


def clean_answer(raw: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", raw.replace("\r\n", "\n")).strip()[:MAX_ANSWER_CHARS]


def score_answer(
    answer: str,
    *,
    requirement_text: str,
    evidence_texts: Sequence[str],
    job_words: Iterable[str],
    next_topic: str | None,
) -> Feedback:
    """Feedback on one answer, from the answer itself. It says what is strong and what to add, in
    plain sentences. It never rates the person, only the answer, and it names any claim in the
    answer that is not in the person's evidence so they can fix the answer or the profile."""
    words = len(answer.split())
    situation = bool(_SITUATION.search(answer))
    action = bool(_ACTION.search(answer))
    result = bool(_RESULT.search(answer))
    have = sum((situation, action, result))
    if not 25 <= words <= 250:
        structure = min(have, 1)
        structure_note = (
            "Too short to follow. Aim for about 60 to 200 words."
            if words < 25
            else "Long. Cut it to the situation, what you did and what changed."
        )
    else:
        structure = have
        missing = [
            name
            for name, present in (
                ("the situation", situation),
                ("what you did", action),
                ("the result", result),
            )
            if not present
        ]
        structure_note = (
            "Clear: situation, action and result are all there."
            if not missing
            else "Add " + " and ".join(missing) + "."
        )
    numbers = len(_NUMBER.findall(answer))
    evidence_tokens = _tokens(" ".join(evidence_texts))
    named = len(_tokens(answer) & evidence_tokens)
    specificity = min(
        3, (1 if numbers else 0) + (1 if named >= 2 else 0) + (1 if named >= 5 else 0)
    )
    specificity_note = (
        "Specific: it has numbers and real names in it."
        if specificity >= 2
        else "Add a number (how many, how much, how long) and the names of the tools or people involved."
    )
    wanted = _tokens(requirement_text)
    overlap = len(wanted & _tokens(answer))
    relevance = 3 if wanted and overlap >= max(2, len(wanted) // 2) else 2 if overlap >= 1 else 0
    relevance_note = (
        "It speaks to what the posting asks."
        if relevance >= 2
        else "It does not clearly address what the posting asks. Use its words."
    )
    verification = verify_text(
        [answer], before=[requirement_text], evidence=evidence_texts, job_words=job_words
    )
    unsupported = tuple(c.text for c in verification.unsupported)
    honesty = (
        3 if not unsupported else 2 if len(unsupported) == 1 else 1 if len(unsupported) <= 3 else 0
    )
    honesty_note = (
        "Everything specific in it is in your profile."
        if not unsupported
        else "These are not in your profile: "
        + ", ".join(unsupported[:5])
        + ". Add them to your profile if true, or take them out."
    )
    follow = (
        f"Next, practise this one: {next_topic}"
        if next_topic
        else "You have been through every topic. Repeat the weakest answer, aiming for a number and a result."
    )
    return Feedback(
        rubric=(
            Rubric("Structure", structure, structure_note),
            Rubric("Specifics", specificity, specificity_note),
            Rubric("Relevance", relevance, relevance_note),
            Rubric("Honesty", honesty, honesty_note),
        ),
        unsupported_claims=unsupported,
        words=words,
        follow_up=follow,
    )


# ---------------------------------------------------------------- what can go wrong, in words


class PrepErrorCode(StrEnum):
    ANALYSIS_NEEDED = "analysis_needed"
    NO_EVIDENCE = "no_evidence"
    AI_NOT_CONFIGURED = "ai_not_configured"
    AI_UNAVAILABLE = "ai_unavailable"
    AI_BAD_OUTPUT = "ai_bad_output"


PREP_ERROR_MESSAGES: dict[str, str] = {
    PrepErrorCode.ANALYSIS_NEEDED: "Check this job against your evidence first. Preparation is built from what the check found.",
    PrepErrorCode.NO_EVIDENCE: "Your evidence does not support this yet, so there is nothing true to build it from. Add evidence to your profile and check the job again.",
    PrepErrorCode.AI_NOT_CONFIGURED: "The writing service is not set up yet. Try again later.",
    PrepErrorCode.AI_UNAVAILABLE: "The writing service did not answer. Try again in a few minutes.",
    PrepErrorCode.AI_BAD_OUTPUT: "The writing service gave an answer we could not use. Try again.",
}

# These are about the person, so they need evidence to be built from. The others can be written
# about the job alone, and say so where the evidence is thin.
NEEDS_EVIDENCE = frozenset({"resume_questions", "project_questions", "outreach", "referral"})
TEXT_ACTIONS = frozenset({"outreach", "referral"})
MAX_MESSAGE_CHARS = 1200
MIN_MESSAGE_CHARS = 40
