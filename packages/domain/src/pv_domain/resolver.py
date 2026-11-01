"""The source resolver: from a search intent to an honest plan, with no model.

For every source in the registry it decides one of three things, and says why in words that come
from the source's own record:

  search           the source may be searched now: verified, in date, switched on, with an adapter
  import_required  there is no permitted automated search, but the person can import jobs from it
  unavailable      it cannot be used now, with the reason (and the import path, where there is one)

It never substitutes silently. A platform the person named that cannot be searched says so and
offers import. A company is resolved to the registry (pv_domain.company), and its own career system
is preferred when that source can be searched. Otherwise a permitted aggregator that can filter by
company is used, otherwise import. The copy never claims a platform was searched when its jobs were
supplied by the person.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from pv_domain.company import Candidate, Company, CompanyMatch, resolve_company
from pv_domain.search_intent import SearchIntent, countries_in
from pv_domain.sources import (
    DEFAULT_REVIEW_WINDOW_DAYS,
    SourceRecord,
    SourceType,
    adapter_ready,
    unavailable_reason,
)

IMPORT_HINT = "Import jobs by URL, paste, or CSV/XLSX and we will analyze them."


class Outcome(StrEnum):
    SEARCH = "search"
    IMPORT_REQUIRED = "import_required"
    UNAVAILABLE = "unavailable"


class Route(StrEnum):
    FIRST_PARTY = "first_party"
    AGGREGATOR = "aggregator"
    IMPORT = "import"
    CHOOSE = "choose"
    NONE = "none"


@dataclass(frozen=True)
class SourceDecision:
    key: str
    display_name: str
    outcome: Outcome
    message: str
    reason: str | None = None
    import_available: bool = False
    named_by_person: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanyDecision:
    query: str
    status: CompanyMatch
    route: Route
    message: str
    company: Company | None = None
    source_key: str | None = None
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class SearchPlan:
    intent: SearchIntent
    sources: tuple[SourceDecision, ...]
    companies: tuple[CompanyDecision, ...]
    headline: str
    can_search_now: bool
    notes: tuple[str, ...] = field(default=())


def decide_source(
    record: SourceRecord,
    intent: SearchIntent,
    today: date,
    window_days: int = DEFAULT_REVIEW_WINDOW_DAYS,
    *,
    named: bool = False,
) -> SourceDecision:
    name = record.display_name
    import_ok = record.supports_user_import

    def decision(
        outcome: Outcome, message: str, reason: str | None = None, notes: tuple[str, ...] = ()
    ) -> SourceDecision:
        return SourceDecision(record.key, name, outcome, message, reason, import_ok, named, notes)

    if record.source_type == SourceType.USER_IMPORT_ONLY:
        return decision(
            Outcome.IMPORT_REQUIRED,
            f"Automated search for {name} is not available. {IMPORT_HINT}",
            unavailable_reason(record, today, window_days),
        )
    reason = unavailable_reason(record, today, window_days)
    if reason is not None:
        tail = f" You can still import jobs you collected from {name}." if import_ok else ""
        return decision(
            Outcome.UNAVAILABLE, f"{name} is currently unavailable. Reason: {reason}{tail}", reason
        )
    wanted = countries_in(intent.locations)
    if wanted and record.geographic_coverage and not set(wanted) & set(record.geographic_coverage):
        cover = ", ".join(record.geographic_coverage)
        reason = f"It does not cover {', '.join(wanted)}. It covers {cover}."
        return decision(
            Outcome.UNAVAILABLE,
            f"{name} is currently unavailable for this search. Reason: {reason}",
            reason,
        )
    if not adapter_ready(record) or not (record.can("can_search") or record.can("can_enumerate")):
        return decision(
            Outcome.IMPORT_REQUIRED,
            f"Automated search for {name} is not available. {IMPORT_HINT}",
            "Automated search for this source has not been built yet.",
        )
    notes: list[str] = []
    if intent.locations and not record.can("supports_location_filter"):
        notes.append(
            "It cannot filter by location, so results are filtered after they are fetched."
        )
    if intent.companies and not (
        record.can("supports_company_filter") or record.can("can_enumerate")
    ):
        notes.append("It cannot filter by company, so results are filtered after they are fetched.")
    return decision(Outcome.SEARCH, f"Searching {name}", None, tuple(notes))


def _decide_company(
    query: str,
    companies: list[Company],
    decisions: dict[str, SourceDecision],
    records: dict[str, SourceRecord],
) -> CompanyDecision:
    resolved = resolve_company(query, companies)
    if resolved.status == CompanyMatch.UNKNOWN:
        return CompanyDecision(
            query,
            CompanyMatch.UNKNOWN,
            Route.IMPORT,
            f"We do not have {query} in the company list. Import its jobs or paste a posting. {IMPORT_HINT}",
        )
    if resolved.status == CompanyMatch.AMBIGUOUS:
        names = ", ".join(c.company.canonical_name for c in resolved.candidates)
        return CompanyDecision(
            query,
            CompanyMatch.AMBIGUOUS,
            Route.CHOOSE,
            f"Which one did you mean by {query}? {names}.",
            candidates=resolved.candidates,
        )
    company = resolved.chosen
    if company is None:
        return CompanyDecision(query, CompanyMatch.UNKNOWN, Route.IMPORT, IMPORT_HINT)
    own = company.ats_platform
    if own and own in decisions and decisions[own].outcome == Outcome.SEARCH:
        return CompanyDecision(
            query,
            CompanyMatch.RESOLVED,
            Route.FIRST_PARTY,
            f"Using the company's own career system ({decisions[own].display_name}).",
            company=company,
            source_key=own,
            candidates=resolved.candidates,
        )
    for key, decision in decisions.items():
        if decision.outcome == Outcome.SEARCH and records[key].can("supports_company_filter"):
            return CompanyDecision(
                query,
                CompanyMatch.RESOLVED,
                Route.AGGREGATOR,
                f"{company.canonical_name} has no career system we can search, so {decision.display_name} is used for it.",
                company=company,
                source_key=key,
                candidates=resolved.candidates,
            )
    return CompanyDecision(
        query,
        CompanyMatch.RESOLVED,
        Route.IMPORT,
        f"No permitted source can be searched for {company.canonical_name}. {IMPORT_HINT}",
        company=company,
        candidates=resolved.candidates,
    )


def plan_search(
    intent: SearchIntent,
    sources: list[SourceRecord],
    companies: list[Company],
    today: date,
    window_days: int = DEFAULT_REVIEW_WINDOW_DAYS,
) -> SearchPlan:
    records = {s.key: s for s in sources}
    notes = list(intent.notes)
    named = {k for k in intent.sources if k != "all_permitted"}
    chosen = sources if intent.all_sources else [records[k] for k in intent.sources if k in records]
    decisions = {
        r.key: decide_source(r, intent, today, window_days, named=r.key in named) for r in chosen
    }
    for key in sorted(named - set(records)):
        notes.append(f"{key} is not a source we know. It was ignored.")
    company_decisions = tuple(
        _decide_company(q, companies, decisions, records) for q in intent.companies
    )
    ordered = tuple(
        sorted(
            decisions.values(),
            key=lambda d: (
                {Outcome.SEARCH: 0, Outcome.IMPORT_REQUIRED: 1, Outcome.UNAVAILABLE: 2}[d.outcome],
                d.display_name,
            ),
        )
    )
    searching = [d for d in ordered if d.outcome == Outcome.SEARCH]
    if searching:
        headline = "Searching " + ", ".join(d.display_name for d in searching) + "."
    else:
        headline = "No source can be searched automatically for this yet. You can import jobs and we will analyze them."
    return SearchPlan(intent, ordered, company_decisions, headline, bool(searching), tuple(notes))
