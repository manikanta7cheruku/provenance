"""A search, as a structure. Words become filters once, then code and SQL do the rest.

A person types what they want in their own words. One model call (class L) turns that into a
SearchIntent. Everything after that is code: the model is not responsible for filtering, choosing a
company or choosing a source. This module cleans whatever the model returned: values that are not in
the allowed lists are dropped, with a note, and the rest is kept, so a slightly wrong answer still
gives a usable and honest search.

What the person's profile says about work authorization is added by the caller from the profile. It
is never read from the typed text, so it cannot be changed by wording.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pv_domain.job import EMPLOYMENT_TYPES

WORK_MODES = ("any", "remote", "hybrid", "onsite")
PERIODS = ("year", "month", "hour")
ALL_PERMITTED = "all_permitted"
MAX_QUERY_CHARS = 500
MAX_ITEMS = 12
MAX_ITEM_CHARS = 80

# Country names a search can mention, with the spellings people use.
COUNTRIES = {
    "India": ("india", "bharat"),
    "United States": ("united states", "usa", "us", "u.s.", "america"),
    "Canada": ("canada",),
    "United Kingdom": ("united kingdom", "uk", "u.k.", "britain", "england"),
    "Germany": ("germany",),
    "United Arab Emirates": ("united arab emirates", "uae", "dubai", "abu dhabi"),
    "Singapore": ("singapore",),
    "Australia": ("australia",),
    "Bangladesh": ("bangladesh",),
    "Sri Lanka": ("sri lanka",),
    "Nepal": ("nepal",),
    "Pakistan": ("pakistan",),
}
_WORDS = re.compile(r"[a-z.]+(?: [a-z.]+)*")

# Cities and regions that name a country by themselves.
PLACES = {
    "bengaluru": "India", "bangalore": "India", "mumbai": "India", "delhi": "India",
    "hyderabad": "India", "chennai": "India", "pune": "India", "kolkata": "India",
    "london": "United Kingdom", "toronto": "Canada", "berlin": "Germany",
    "new york": "United States", "san francisco": "United States",
}  # fmt: skip


@dataclass(frozen=True)
class Compensation:
    minimum: int
    currency: str
    period: str


@dataclass(frozen=True)
class SearchIntent:
    roles: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    min_years: int | None = None
    max_years: int | None = None
    locations: tuple[str, ...] = ()
    work_mode: str = "any"
    employment_types: tuple[str, ...] = ()
    compensation: Compensation | None = None
    companies: tuple[str, ...] = ()
    sources: tuple[str, ...] = (ALL_PERMITTED,)
    exclusions: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def all_sources(self) -> bool:
        return self.sources == (ALL_PERMITTED,)


def countries_in(locations: tuple[str, ...]) -> tuple[str, ...]:
    """The countries a list of places refers to, found by plain lookup. No model."""
    found: list[str] = []
    for place in locations:
        lowered = place.lower()
        words = " ".join(_WORDS.findall(lowered))
        for country, names in COUNTRIES.items():
            named = any(re.search(rf"(?:^|[ ,]){re.escape(n)}(?:$|[ ,])", words) for n in names)
            if named and country not in found:
                found.append(country)
        for city, country in PLACES.items():
            if city in lowered and country not in found:
                found.append(country)
    return tuple(found)


def _strings(value: Any, label: str, notes: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        notes.append(f"Ignored {label}: it was not a list.")
        return ()
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = " ".join("".join(ch for ch in item if ch >= " " and ch != "\x7f").split())
        if text and len(text) <= MAX_ITEM_CHARS and text.lower() not in {o.lower() for o in out}:
            out.append(text)
    if len(out) > MAX_ITEMS:
        notes.append(f"Kept the first {MAX_ITEMS} of your {label}.")
    return tuple(out[:MAX_ITEMS])


def _years(value: Any, label: str, notes: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 60:
        notes.append(f"Ignored {label}: use a whole number from 0 to 60.")
        return None
    return int(value)


def clean_intent(raw: Any, source_keys: set[str] | None = None) -> SearchIntent:
    """A SearchIntent from whatever the model returned. It never raises: bad parts are dropped and noted."""
    notes: list[str] = []
    if not isinstance(raw, dict):
        return SearchIntent(notes=("The search could not be understood.",))
    min_years = _years(raw.get("min_years"), "the minimum years", notes)
    max_years = _years(raw.get("max_years"), "the maximum years", notes)
    if min_years is not None and max_years is not None and min_years > max_years:
        notes.append("The minimum years was above the maximum, so both were ignored.")
        min_years = max_years = None
    work_mode = raw.get("work_mode", "any")
    if work_mode not in WORK_MODES:
        notes.append("Ignored the work mode: choose remote, hybrid, onsite or any.")
        work_mode = "any"
    types = tuple(
        t
        for t in _strings(raw.get("employment_types"), "employment types", notes)
        if t in EMPLOYMENT_TYPES
    )
    pay = raw.get("compensation")
    compensation: Compensation | None = None
    if isinstance(pay, dict):
        amount, currency, period = pay.get("min"), pay.get("currency"), pay.get("period", "year")
        if (
            isinstance(amount, int)
            and not isinstance(amount, bool)
            and amount > 0
            and isinstance(currency, str)
            and re.fullmatch(r"[A-Za-z]{3}", currency)
            and period in PERIODS
        ):
            compensation = Compensation(amount, currency.upper(), period)
        else:
            notes.append(
                "Ignored the pay: it needs an amount, a three letter currency and a period."
            )
    sources_raw = raw.get("sources", ALL_PERMITTED)
    sources: tuple[str, ...] = (ALL_PERMITTED,)
    if isinstance(sources_raw, list):
        picked = _strings(sources_raw, "sources", notes)
        if picked:
            sources = tuple(s.lower() for s in picked)
    elif sources_raw not in (ALL_PERMITTED, None):
        notes.append("Ignored the sources: use a list of source names.")
    return SearchIntent(
        roles=_strings(raw.get("roles"), "roles", notes),
        skills=_strings(raw.get("skills"), "skills", notes),
        min_years=min_years,
        max_years=max_years,
        locations=_strings(raw.get("locations"), "locations", notes),
        work_mode=str(work_mode),
        employment_types=types,
        compensation=compensation,
        companies=_strings(raw.get("companies"), "companies", notes),
        sources=sources,
        exclusions=_strings(raw.get("exclusions"), "exclusions", notes),
        notes=tuple(notes),
    )


def intent_to_dict(intent: SearchIntent) -> dict[str, Any]:
    return {
        "roles": list(intent.roles),
        "skills": list(intent.skills),
        "min_years": intent.min_years,
        "max_years": intent.max_years,
        "locations": list(intent.locations),
        "work_mode": intent.work_mode,
        "employment_types": list(intent.employment_types),
        "compensation": (
            {
                "min": intent.compensation.minimum,
                "currency": intent.compensation.currency,
                "period": intent.compensation.period,
            }
            if intent.compensation
            else None
        ),
        "companies": list(intent.companies),
        "sources": [ALL_PERMITTED] if intent.all_sources else list(intent.sources),
        "exclusions": list(intent.exclusions),
    }


def clean_query(text: Any) -> str | None:
    """The typed search, tidied, or None when it is empty or too long."""
    if not isinstance(text, str):
        return None
    tidy = " ".join("".join(ch for ch in text if ch >= " " and ch != "\x7f").split())
    return tidy if tidy and len(tidy) <= MAX_QUERY_CHARS else None
