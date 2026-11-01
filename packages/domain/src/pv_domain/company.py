"""The company registry and deterministic company resolution.

A person types a company name. Code decides which registry company it is, in this order:
  1. an exact alias match (ignoring case),
  2. a match after normalising (punctuation and legal suffixes removed),
  3. trigram similarity, accepted only when one company is clearly ahead.
When two or more are close, nothing is chosen: the candidates go back to the person. A model never
chooses a company. The same input and the same registry always give the same answer.

Pure code over a list of companies. The registry is small (hundreds), so it is compared in memory.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

# Words that say what kind of legal entity a name is, and nothing about which company it is.
_SUFFIXES = frozenset(
    [
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "pvt",
        "private",
        "plc",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "ag",
        "sa",
        "technologies",
        "technology",
        "tech",
        "labs",
    ]
)
_NON_WORD = re.compile(r"[^a-z0-9]+")

ACCEPT_SCORE = 0.7
ACCEPT_LEAD = 0.2
CANDIDATE_SCORE = 0.45
MAX_CANDIDATES = 5


class CompanyMatch(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Company:
    key: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    domain: str | None = None
    career_url: str | None = None
    ats_platform: str | None = None  # a source key such as "greenhouse"
    ats_board_id: str | None = None
    industry: str | None = None
    country: str | None = None
    last_verified_at: str | None = None


@dataclass(frozen=True)
class Candidate:
    company: Company
    score: float
    method: str  # "alias", "normalized" or "similar"


@dataclass(frozen=True)
class CompanyResolution:
    query: str
    status: CompanyMatch
    chosen: Company | None
    method: str | None
    candidates: tuple[Candidate, ...]


def normalize(name: str) -> str:
    words = [w for w in _NON_WORD.split(name.lower()) if w]
    kept = [w for w in words if w not in _SUFFIXES]
    return " ".join(kept or words)


def _trigrams(text: str) -> set[str]:
    padded = f"  {text} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def similarity(a: str, b: str) -> float:
    """Share of trigrams two normalised names have in common, from 0 to 1."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _containment(a: str, b: str) -> float:
    """How much of the shorter name sits inside the longer one. A prefix such as Tata scores high."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def resolve_company(query: str, companies: list[Company]) -> CompanyResolution:
    text = " ".join(query.split())
    if not text:
        return CompanyResolution(query, CompanyMatch.UNKNOWN, None, None, ())
    lowered = text.lower()
    exact = [c for c in companies if lowered in {n.lower() for n in (c.canonical_name, *c.aliases)}]
    if len(exact) == 1:
        return CompanyResolution(
            text, CompanyMatch.RESOLVED, exact[0], "alias", (Candidate(exact[0], 1.0, "alias"),)
        )
    if len(exact) > 1:
        cands = tuple(Candidate(c, 1.0, "alias") for c in exact[:MAX_CANDIDATES])
        return CompanyResolution(text, CompanyMatch.AMBIGUOUS, None, None, cands)
    wanted = normalize(text)
    normed = [
        c for c in companies if wanted in {normalize(n) for n in (c.canonical_name, *c.aliases)}
    ]
    if len(normed) == 1:
        return CompanyResolution(
            text,
            CompanyMatch.RESOLVED,
            normed[0],
            "normalized",
            (Candidate(normed[0], 1.0, "normalized"),),
        )
    if len(normed) > 1:
        cands = tuple(Candidate(c, 1.0, "normalized") for c in normed[:MAX_CANDIDATES])
        return CompanyResolution(text, CompanyMatch.AMBIGUOUS, None, None, cands)
    names = {c.key: [normalize(n) for n in (c.canonical_name, *c.aliases)] for c in companies}
    scored = sorted(
        (
            Candidate(
                c,
                max(max(similarity(wanted, n), _containment(wanted, n)) for n in names[c.key]),
                "similar",
            )
            for c in companies
        ),
        key=lambda cand: (-cand.score, cand.company.key),
    )
    near = tuple(c for c in scored if c.score >= CANDIDATE_SCORE)[:MAX_CANDIDATES]
    if not near:
        return CompanyResolution(text, CompanyMatch.UNKNOWN, None, None, ())
    # Only a close spelling is accepted by itself. A name that merely starts the same is a candidate.
    close = [(c, max(similarity(wanted, n) for n in names[c.company.key])) for c in near]
    close.sort(key=lambda pair: (-pair[1], pair[0].company.key))
    lead = close[0][1] - (close[1][1] if len(close) > 1 else 0.0)
    if close[0][1] >= ACCEPT_SCORE and lead >= ACCEPT_LEAD:
        return CompanyResolution(text, CompanyMatch.RESOLVED, close[0][0].company, "similar", near)
    return CompanyResolution(text, CompanyMatch.AMBIGUOUS, None, None, near)
