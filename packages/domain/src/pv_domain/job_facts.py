"""Checking what a model said about a job posting against the posting itself.

Every fact and every requirement must come with the posting's own words, found in the text. What
cannot be found is dropped and counted, never stored. Values are also checked against their
allowed vocabulary, so the eligibility rules only ever see values they understand.

Pure code: the model's answer comes in as plain dictionaries.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pv_domain.eligibility import Fact, PostingFacts
from pv_domain.job import (
    EMPLOYMENT_TYPES,
    MAX_QUOTE_CHARS,
    MAX_REQUIREMENTS_KEPT,
    REQUIREMENT_CATEGORIES,
    REQUIREMENT_KINDS,
    SENIORITY_LEVELS,
    SPONSORSHIP_VALUES,
    WORK_MODES,
    find_quote,
)
from pv_domain.profile import resume_token_set, significant_tokens

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15,
}  # fmt: skip
_DIGITS = re.compile(r"\d+")
_WORDS = re.compile(r"[a-z]+")

FACT_KEYS = (
    "location",
    "work_mode",
    "employment_type",
    "seniority",
    "min_years_experience",
    "sponsorship",
    "work_authorization_countries",
)


@dataclass
class GroundedJob:
    title: str | None = None
    company: str | None = None
    # key -> {"value": ..., "quote": ..., "start": int, "end": int}
    facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    # dicts with text, kind, category, years_min, quote, quote_start, quote_end
    requirements: list[dict[str, Any]] = field(default_factory=list)
    facts_dropped: int = 0
    requirements_dropped: int = 0
    requirements_proposed: int = 0


def _short(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned if 0 < len(cleaned) <= limit else None


def _years_in_quote(value: int, quote: str) -> bool:
    if any(int(n) == value for n in _DIGITS.findall(quote)):
        return True
    return any(_NUMBER_WORDS.get(word) == value for word in _WORDS.findall(quote.casefold()))


def _fact_value(key: str, raw: Any, quote: str, tokens: frozenset[str]) -> Any | None:
    """The cleaned value if it is allowed for this key, else None."""
    if key == "work_mode":
        return raw if raw in WORK_MODES else None
    if key == "employment_type":
        return raw if raw in EMPLOYMENT_TYPES else None
    if key == "seniority":
        return raw if raw in SENIORITY_LEVELS else None
    if key == "sponsorship":
        return raw if raw in SPONSORSHIP_VALUES else None
    if key == "min_years_experience":
        number = int(raw) if isinstance(raw, int | str) and str(raw).isdigit() else None
        if number is None or not 0 <= number <= 60:
            return None
        return number if _years_in_quote(number, quote) else None
    if key == "location":
        place = _short(raw, 120)
        words = significant_tokens(place) if place else []
        return place if words and all(w in tokens for w in words) else None
    if key == "work_authorization_countries":
        items = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
        cleaned = [c for c in (_short(i, 60) for i in items[:10]) if c]
        return cleaned or None
    return None


def ground_extraction(raw_text: str, proposed: dict[str, Any]) -> GroundedJob:
    """Keep only what the posting itself supports. `proposed` is the validated model answer."""
    tokens = resume_token_set(raw_text)
    out = GroundedJob()

    facts_in = proposed.get("facts") or {}
    for key in ("title", "company"):
        value = _short(facts_in.get(key), 200)
        if value is None:
            continue
        words = significant_tokens(value)
        if words and all(w in tokens for w in words):
            setattr(out, key, value)
        else:
            out.facts_dropped += 1
    for key in FACT_KEYS:
        item = facts_in.get(key)
        if not isinstance(item, dict):
            continue
        quote = item.get("quote")
        span = find_quote(raw_text, quote) if isinstance(quote, str) else None
        value = _fact_value(
            key, item.get("value"), raw_text[span[0] : span[1]] if span else "", tokens
        )
        if span is None or value is None:
            out.facts_dropped += 1
            continue
        out.facts[key] = {
            "value": value,
            "quote": raw_text[span[0] : span[1]],
            "start": span[0],
            "end": span[1],
        }

    seen: set[str] = set()
    for item in (proposed.get("requirements") or [])[:200]:
        out.requirements_proposed += 1
        if not isinstance(item, dict):
            out.requirements_dropped += 1
            continue
        text = _short(item.get("text"), 300)
        quote = item.get("quote")
        span = (
            find_quote(raw_text, quote)
            if isinstance(quote, str) and len(quote) <= MAX_QUOTE_CHARS
            else None
        )
        kind = item.get("kind")
        if text is None or span is None or kind not in REQUIREMENT_KINDS:
            out.requirements_dropped += 1
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        if len(out.requirements) >= MAX_REQUIREMENTS_KEPT:
            out.requirements_dropped += 1
            continue
        category = (
            item.get("category") if item.get("category") in REQUIREMENT_CATEGORIES else "other"
        )
        years = item.get("years_min")
        out.requirements.append(
            {
                "text": text,
                "kind": kind,
                "category": category,
                "years_min": years if isinstance(years, int) and 0 <= years <= 60 else None,
                "quote": raw_text[span[0] : span[1]],
                "quote_start": span[0],
                "quote_end": span[1],
            }
        )
    return out


def posting_facts_from_record(
    raw_text: str, title: str | None, company: str | None, facts: dict[str, Any]
) -> PostingFacts:
    """Rebuild the eligibility input from what was stored."""

    def fact(key: str) -> Fact | None:
        item = facts.get(key)
        if not isinstance(item, dict) or "value" not in item:
            return None
        value = item["value"]
        return Fact(tuple(value) if isinstance(value, list) else value, str(item.get("quote", "")))

    return PostingFacts(
        raw_text=raw_text,
        title=title,
        company=company,
        location=fact("location"),
        work_mode=fact("work_mode"),
        employment_type=fact("employment_type"),
        seniority=fact("seniority"),
        min_years=fact("min_years_experience"),
        sponsorship=fact("sponsorship"),
        authorization_countries=fact("work_authorization_countries"),
    )
