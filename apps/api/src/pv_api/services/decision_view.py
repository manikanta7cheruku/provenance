"""How one job's decision is shown: its state, the actions on offer now, and the note.

Shared by the workbench list and the job page, so both always show the same thing.
"""

from sqlalchemy.orm import Session

from pv_api.schemas import ActionOut, DecisionOut
from pv_domain.eligibility import evaluate_eligibility
from pv_domain.job import JobParseStatus
from pv_domain.job_facts import posting_facts_from_record
from pv_domain.pipeline import ACTION_LABELS, STATE_LABELS, available_actions
from pv_persistence.jobs import load_seeker
from pv_persistence.models import JobDecision, JobPosting
from pv_persistence.workbench import get_decision, state_of


def eligibility_state(db: Session, posting: JobPosting) -> str | None:
    """The job's eligibility state, or None while it has not been read."""
    if posting.parse_status != JobParseStatus.EXTRACTED:
        return None
    prefs, years = load_seeker(db, posting.owner_user_id)
    facts = posting_facts_from_record(
        posting.raw_text, posting.title, posting.company, posting.facts
    )
    return evaluate_eligibility(facts, prefs, years).state.value


def decision_out(decision: JobDecision | None, eligibility: str | None) -> DecisionOut:
    state = state_of(decision)
    return DecisionOut(
        state=state.value,
        state_label=STATE_LABELS[state],
        actions=[
            ActionOut(action=a.value, label=ACTION_LABELS[a])
            for a in available_actions(state, eligibility)
        ],
        note=decision.note if decision else "",
        applied_at=decision.applied_at if decision else None,
        updated_at=decision.updated_at if decision else None,
    )


def decision_for_job(db: Session, posting: JobPosting) -> DecisionOut:
    return decision_out(
        get_decision(db, posting.owner_user_id, posting.id), eligibility_state(db, posting)
    )
