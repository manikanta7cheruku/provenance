"""One person's jobs as workbench rows: what they decided, whether they can take each, and its fit.

Shared by the workbench list (the API) and the shortlist email (the worker), so both always agree on
who is eligible for what and how well a job fits. Call inside tenant_session.
"""

import uuid

from sqlalchemy.orm import Session

from pv_domain.eligibility import evaluate_eligibility
from pv_domain.job import JobParseStatus, job_ui_state
from pv_domain.job_facts import posting_facts_from_record
from pv_domain.pipeline import WorkRow
from pv_persistence.jobs import list_postings, load_seeker
from pv_persistence.models import JobDecision, JobPosting
from pv_persistence.workbench import decisions_for, fit_scores, state_of


def fact_value(posting: JobPosting, key: str) -> str | None:
    item = posting.facts.get(key)
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    return (
        ", ".join(value) if isinstance(value, list) else str(value) if value is not None else None
    )


def make_row(
    posting: JobPosting, decision: JobDecision | None, eligibility: str | None, band: str | None
) -> WorkRow:
    return WorkRow(
        id=str(posting.id),
        title=posting.title or "",
        company=posting.company or "",
        source_name=posting.source_name,
        acquisition_method=posting.acquisition_method,
        work_mode=fact_value(posting, "work_mode"),
        location=fact_value(posting, "location") or "",
        employment_type=fact_value(posting, "employment_type"),
        seniority=fact_value(posting, "seniority"),
        eligibility=eligibility,
        band=band,
        reading=job_ui_state(posting.parse_status).value,
        state=state_of(decision).value,
        created_at=posting.created_at,
        applied_at=decision.applied_at if decision else None,
        note=decision.note if decision else "",
    )


def load_rows(
    db: Session, owner: uuid.UUID, limit: int
) -> tuple[list[JobPosting], list[WorkRow], dict[uuid.UUID, str]]:
    """The newest `limit` postings, their rows, and the first scoring reason of each job that has a
    complete evidence check (the sentence that says how many requirements are supported)."""
    postings = list_postings(db, owner, limit=limit)
    decisions = decisions_for(db, owner)
    prefs, years = load_seeker(db, owner)
    eligibility: dict[uuid.UUID, str] = {}
    for posting in postings:
        if posting.parse_status == JobParseStatus.EXTRACTED:
            facts = posting_facts_from_record(
                posting.raw_text, posting.title, posting.company, posting.facts
            )
            eligibility[posting.id] = evaluate_eligibility(facts, prefs, years).state.value
    scores = fit_scores(db, owner, {p: s != "not_eligible" for p, s in eligibility.items()})
    rows = [
        make_row(
            p,
            decisions.get(p.id),
            eligibility.get(p.id),
            scores[p.id].band.value if p.id in scores else None,
        )
        for p in postings
    ]
    reasons = {p: s.reasons[0] for p, s in scores.items() if s.reasons}
    return postings, rows, reasons
