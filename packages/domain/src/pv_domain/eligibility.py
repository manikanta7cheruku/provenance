"""Deterministic eligibility: can this person take this job at all?

Five gates, each answered by plain code from facts that were found in the posting (with their
quotes) and from the person's own answers. No model is involved and no score is involved: a hard
blocker is stated as a blocker, in words, and is never averaged into a number.

States per gate and overall:
  eligible              nothing in the way
  not_eligible          a hard blocker, with the reason and the quote that proves it
  uncertain             worth a human look, the facts do not settle it
  requires_user_input   we cannot tell until the person answers a question

The overall state is the most serious gate state, in the order above reversed:
not_eligible, requires_user_input, uncertain, eligible.

The rules are versioned (RULES_VERSION). Results are computed when read, so a changed answer or a
new rule version applies at once and nothing stale is stored.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

RULES_VERSION = "eligibility-1"

# A requirement this many years above the person's experience is treated as a hard blocker.
HARD_EXPERIENCE_GAP_YEARS = 5.0
# Above this gap the person is told to take a closer look.
REVIEW_EXPERIENCE_GAP_YEARS = 2.0
# Below this many years asked for, a missing experience record is not worth a question.
MIN_YEARS_WORTH_ASKING = 2.0

_COUNTRY_ALIASES = {
    "in": "india", "ind": "india", "bharat": "india",
    "us": "united states", "usa": "united states", "u.s.": "united states",
    "u.s.a.": "united states", "america": "united states", "united states of america": "united states",
    "uk": "united kingdom", "u.k.": "united kingdom", "gb": "united kingdom", "britain": "united kingdom",
    "great britain": "united kingdom", "england": "united kingdom",
    "uae": "united arab emirates", "ae": "united arab emirates",
    "ca": "canada", "sg": "singapore", "au": "australia", "de": "germany", "deutschland": "germany",
}  # fmt: skip

_WORD = re.compile(r"[a-z0-9]+")
_SMALL_WORDS = frozenset({"the", "of", "and", "area", "region", "metropolitan"})


class EligibilityState(StrEnum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNCERTAIN = "uncertain"
    REQUIRES_USER_INPUT = "requires_user_input"


_SEVERITY = {
    EligibilityState.NOT_ELIGIBLE: 3,
    EligibilityState.REQUIRES_USER_INPUT: 2,
    EligibilityState.UNCERTAIN: 1,
    EligibilityState.ELIGIBLE: 0,
}


@dataclass(frozen=True)
class Fact:
    """A value the posting states, with the words that prove it."""

    value: str | int | tuple[str, ...]
    quote: str


@dataclass(frozen=True)
class PostingFacts:
    raw_text: str
    title: str | None = None
    company: str | None = None
    location: Fact | None = None
    work_mode: Fact | None = None
    employment_type: Fact | None = None
    seniority: Fact | None = None
    min_years: Fact | None = None
    sponsorship: Fact | None = None
    authorization_countries: Fact | None = None


@dataclass(frozen=True)
class SeekerPreferences:
    authorized_countries: tuple[str, ...] = ()
    needs_sponsorship: bool | None = None
    locations: tuple[str, ...] = ()
    open_to_relocate: bool | None = None
    remote_preference: str | None = None
    employment_types: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResult:
    gate: str
    label: str
    state: EligibilityState
    reason: str
    # The posting's own words behind the result, when there are any.
    posting_quote: str | None = None


@dataclass(frozen=True)
class EligibilityResult:
    state: EligibilityState
    gates: tuple[GateResult, ...] = field(default_factory=tuple)
    rules_version: str = RULES_VERSION


def _country(value: str) -> str:
    cleaned = " ".join(value.casefold().split())
    return _COUNTRY_ALIASES.get(cleaned, cleaned)


def _countries(values: tuple[str, ...] | str) -> set[str]:
    items = (values,) if isinstance(values, str) else values
    return {_country(v) for v in items if v.strip()}


def _place_tokens(value: str) -> set[str]:
    return {t for t in _WORD.findall(value.casefold()) if t not in _SMALL_WORDS}


_COUNTRY_WORDS = frozenset(
    {
        "india",
        "united",
        "states",
        "kingdom",
        "arab",
        "emirates",
        "canada",
        "singapore",
        "australia",
        "germany",
    }
)


def _same_place(posting_location: str, wanted: str) -> bool:
    """Do two place names point at the same place? One may be a part of the other
    ("Bengaluru" and "Bengaluru, India"), or they may share a city name. A shared country alone
    does not make two cities the same, but a wanted place that is only a country does match a
    city inside it."""
    a, b = _place_tokens(posting_location), _place_tokens(wanted)
    if not a or not b:
        return False
    return a <= b or b <= a or bool((a & b) - _COUNTRY_WORDS)


def _join(items: set[str] | list[str]) -> str:
    ordered = sorted(items)
    return (
        ", ".join(ordered[:-1]) + (" and " if len(ordered) > 1 else "") + ordered[-1]
        if ordered
        else ""
    )


def _g(
    gate: str, label: str, state: EligibilityState, reason: str, quote: str | None = None
) -> GateResult:
    return GateResult(gate, label, state, reason, quote)


E = EligibilityState


def _authorization(f: PostingFacts, p: SeekerPreferences) -> GateResult:
    label = "Work authorization and sponsorship"
    sponsorship = f.sponsorship.value if f.sponsorship else None
    quote = (f.sponsorship.quote if f.sponsorship else None) or (
        f.authorization_countries.quote if f.authorization_countries else None
    )
    if sponsorship == "not_offered" and p.needs_sponsorship is True:
        return _g("authorization", label, E.NOT_ELIGIBLE,
                  "The posting says it does not sponsor work visas, and you said you need sponsorship.",
                  f.sponsorship.quote if f.sponsorship else None)  # fmt: skip
    if f.authorization_countries:
        required = _countries(f.authorization_countries.value)  # type: ignore[arg-type]
        if not p.authorized_countries:
            return _g("authorization", label, E.REQUIRES_USER_INPUT,
                      f"The posting requires permission to work in {_join(required)}. Add the countries "
                      "where you can work without a visa in your preferences.", quote)  # fmt: skip
        mine = _countries(p.authorized_countries)
        if required & mine:
            return _g("authorization", label, E.ELIGIBLE,
                      f"You can work in {_join(required & mine)} without a visa, which the posting requires.",
                      quote)  # fmt: skip
        if sponsorship == "not_offered":
            return _g("authorization", label, E.NOT_ELIGIBLE,
                      f"The posting requires permission to work in {_join(required)}, you list "
                      f"{_join(mine)}, and the posting does not sponsor visas.", quote)  # fmt: skip
        if sponsorship == "offered":
            return _g("authorization", label, E.UNCERTAIN,
                      f"The posting requires permission to work in {_join(required)}, which you do not "
                      "list. It says it offers visa sponsorship, so ask what that covers.", quote)  # fmt: skip
        return _g("authorization", label, E.UNCERTAIN,
                  f"The posting requires permission to work in {_join(required)}, which you do not "
                  "list. It does not say whether it sponsors visas.", quote)  # fmt: skip
    if sponsorship == "not_offered" and p.needs_sponsorship is None:
        return _g("authorization", label, E.REQUIRES_USER_INPUT,
                  "The posting says it does not sponsor work visas. Tell us in your preferences whether "
                  "you need sponsorship.", quote)  # fmt: skip
    if p.needs_sponsorship is True and sponsorship is None:
        return _g("authorization", label, E.UNCERTAIN,
                  "You need sponsorship. The posting does not say whether it sponsors visas.")  # fmt: skip
    if p.needs_sponsorship is True and sponsorship == "offered":
        return _g(
            "authorization",
            label,
            E.ELIGIBLE,
            "You need sponsorship and the posting offers it.",
            quote,
        )
    return _g(
        "authorization", label, E.ELIGIBLE, "The posting states no work authorization requirement."
    )


def _location(f: PostingFacts, p: SeekerPreferences) -> GateResult:
    label = "Location and work mode"
    mode = f.work_mode.value if f.work_mode else None
    place = f.location.value if f.location else None
    quote = (f.work_mode.quote if f.work_mode else None) or (
        f.location.quote if f.location else None
    )
    if mode is None and place is None:
        return _g("location", label, E.UNCERTAIN,
                  "The posting does not say where the work happens or whether it is remote.")  # fmt: skip
    if mode == "remote":
        return _g("location", label, E.ELIGIBLE, "The role is remote.", quote)
    mode_word = {"hybrid": "hybrid", "onsite": "on-site"}.get(str(mode), "in person")
    if place is None:
        return _g("location", label, E.UNCERTAIN,
                  f"The role is {mode_word}, but the posting does not name a place.", quote)  # fmt: skip
    place = str(place)
    if any(_same_place(place, wanted) for wanted in p.locations):
        state, reason = E.ELIGIBLE, f"The role is {mode_word} in {place}, a place you listed."
    elif p.open_to_relocate is True:
        state, reason = (
            E.ELIGIBLE,
            f"The role is {mode_word} in {place}, and you are open to relocating.",
        )
    elif p.open_to_relocate is False:
        return _g("location", label, E.NOT_ELIGIBLE,
                  f"The role is {mode_word} in {place}, which is not on your list, and you would not "
                  "relocate.", quote)  # fmt: skip
    else:
        return _g("location", label, E.REQUIRES_USER_INPUT,
                  f"The role is {mode_word} in {place}. Tell us the places you would work, or whether "
                  "you would relocate.", quote)  # fmt: skip
    if p.remote_preference == "remote":
        return _g("location", label, E.UNCERTAIN,
                  f"{reason} You said you prefer remote work, so review it.", quote)  # fmt: skip
    return _g("location", label, state, reason, quote)


def _snippet(text: str, start: int, end: int, radius: int = 50) -> str:
    lo, hi = max(0, start - radius), min(len(text), end + radius)
    return ("..." if lo else "") + " ".join(text[lo:hi].split()) + ("..." if hi < len(text) else "")


def _exclusions(f: PostingFacts, p: SeekerPreferences) -> GateResult:
    label = "Things you chose to avoid"
    if not p.exclusions:
        return _g("exclusions", label, E.ELIGIBLE, "You have not listed anything to avoid.")
    haystacks = [("company", f.company or ""), ("title", f.title or ""), ("posting", f.raw_text)]
    for term in p.exclusions:
        cleaned = " ".join(term.split())
        if not cleaned:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(cleaned)}(?!\w)", re.IGNORECASE)
        for source, text in haystacks:
            match = pattern.search(text)
            if match:
                where = (
                    "the company name"
                    if source == "company"
                    else ("the job title" if source == "title" else "the posting")
                )
                return _g("exclusions", label, E.NOT_ELIGIBLE,
                          f'{where.capitalize()} mentions "{cleaned}", which you chose to avoid.',
                          _snippet(text, match.start(), match.end()))  # fmt: skip
    return _g(
        "exclusions", label, E.ELIGIBLE, f"None of the {len(p.exclusions)} things you avoid appear."
    )


def _employment(f: PostingFacts, p: SeekerPreferences) -> GateResult:
    label = "Kind of work"
    kind = str(f.employment_type.value) if f.employment_type else None
    quote = f.employment_type.quote if f.employment_type else None
    nice = {"full_time": "full time", "part_time": "part time", "internship": "an internship",
            "contract": "contract", "freelance": "freelance"}  # fmt: skip
    if not p.employment_types:
        return _g("employment", label, E.ELIGIBLE, "You have not limited the kind of work.", quote)
    if kind is None:
        return _g(
            "employment", label, E.UNCERTAIN, "The posting does not say what kind of work it is."
        )
    if kind in p.employment_types:
        return _g(
            "employment",
            label,
            E.ELIGIBLE,
            f"The role is {nice.get(kind, kind)}, which you accept.",
            quote,
        )
    accepted = _join([nice.get(t, t) for t in p.employment_types])
    return _g("employment", label, E.NOT_ELIGIBLE,
              f"The role is {nice.get(kind, kind)}. You said you would consider {accepted}.", quote)  # fmt: skip


def _fmt(years: float) -> str:
    return f"{years:g}"


def _seniority(f: PostingFacts, p: SeekerPreferences, years: float | None) -> GateResult:
    label = "Experience asked for"
    need = int(f.min_years.value) if f.min_years else None  # type: ignore[arg-type]
    level = str(f.seniority.value) if f.seniority else None
    quote = (f.min_years.quote if f.min_years else None) or (
        f.seniority.quote if f.seniority else None
    )
    if need is None and level is None:
        return _g("seniority", label, E.ELIGIBLE, "The posting states no experience requirement.")
    if need is not None:
        if years is None:
            if need >= MIN_YEARS_WORTH_ASKING:
                return _g("seniority", label, E.REQUIRES_USER_INPUT,
                          f"The posting asks for {need} years of experience. Add dates to your work and "
                          "internship entries so we can compare.", quote)  # fmt: skip
            return _g(
                "seniority",
                label,
                E.ELIGIBLE,
                f"The posting asks for {need} years, a low bar.",
                quote,
            )
        gap = need - years
        if gap >= HARD_EXPERIENCE_GAP_YEARS:
            return _g("seniority", label, E.NOT_ELIGIBLE,
                      f"The posting asks for at least {need} years of experience. Your profile shows about "
                      f"{_fmt(years)}.", quote)  # fmt: skip
        if gap > REVIEW_EXPERIENCE_GAP_YEARS:
            return _g("seniority", label, E.UNCERTAIN,
                      f"The posting asks for {need} years. Your profile shows about {_fmt(years)}. Many "
                      "employers accept less, so review it.", quote)  # fmt: skip
        return _g("seniority", label, E.ELIGIBLE,
                  f"The posting asks for {need} years. Your profile shows about {_fmt(years)}.", quote)  # fmt: skip
    if level in ("senior", "lead") and years is not None and years < MIN_YEARS_WORTH_ASKING:
        return _g("seniority", label, E.UNCERTAIN,
                  f"This is a {level} role and your profile shows about {_fmt(years)} years.", quote)  # fmt: skip
    return _g(
        "seniority", label, E.ELIGIBLE, "The posting names a level but no number of years.", quote
    )


def evaluate_eligibility(
    facts: PostingFacts, preferences: SeekerPreferences, candidate_years: float | None
) -> EligibilityResult:
    """Run every gate. Never raises: missing information becomes an honest state, not an error."""
    gates = (
        _authorization(facts, preferences),
        _location(facts, preferences),
        _exclusions(facts, preferences),
        _employment(facts, preferences),
        _seniority(facts, preferences, candidate_years),
    )
    overall = max((g.state for g in gates), key=lambda s: _SEVERITY[s])
    ordered = tuple(sorted(gates, key=lambda g: -_SEVERITY[g.state]))
    return EligibilityResult(overall, ordered)
