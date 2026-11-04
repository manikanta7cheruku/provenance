"""Duplicates, links and sightings, as people and administrators see them.

A person sees where else a posting they pasted appears, why the product thinks so, and can say it is
the same job or not. Those decisions are theirs alone (Row Level Security). An administrator sees
links between fetched jobs and can confirm a suggested one or undo any.
"""

import uuid
from datetime import date

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    AdminLinkOut,
    JobMatchesOut,
    LinkedJobOut,
    PostingMatchOut,
    SightingOut,
)
from pv_api.services.job_service import not_found
from pv_config import Settings
from pv_domain.failures import FailureClass
from pv_persistence.audit import record_audit
from pv_persistence.dedupe import (
    PostingMatch,
    decide_posting_link,
    get_link,
    list_links,
    posting_matches,
    set_link_state,
)
from pv_persistence.jobs import get_posting
from pv_persistence.models import JobPosting, JobSource, SourceJob
from pv_persistence.tenancy import tenant_session

HOW = {"user_paste": "Pasted by you"}


def _today() -> date:
    return date.today()


def public_sighting(job: SourceJob, source: JobSource) -> SightingOut:
    return SightingOut(
        kind="public",
        source_name=source.display_name,
        board_id=job.board_id,
        title=job.title,
        location=job.location,
        url=job.url,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        seen_count=job.seen_count,
        closed=job.closed_at is not None,
        how=f"Published by {source.display_name}",
    )


def _yours(posting: JobPosting) -> SightingOut:
    return SightingOut(
        kind="yours",
        source_name=posting.source_name,
        board_id=None,
        title=posting.title or "Untitled",
        location="",
        url=posting.source_url,
        first_seen_at=posting.created_at,
        last_seen_at=posting.updated_at,
        seen_count=1,
        closed=False,
        how=HOW.get(posting.acquisition_method, "Added by you"),
    )


def _match_out(m: PostingMatch) -> PostingMatchOut:
    return PostingMatchOut(
        group_id=m.group_id,
        title=m.job.title,
        company_name=m.job.company_name,
        location=m.job.location,
        source_name=m.source.display_name,
        url=m.job.url,
        method=m.match.method,
        score=m.match.score,
        reason=m.match.reason,
        state=m.state,
        sightings=[public_sighting(j, s) for j, s in m.members],
    )


def _view(db: Session, posting: JobPosting, settings: Settings) -> JobMatchesOut:
    found = posting_matches(db, posting, _today(), settings.source_review_window_days)
    linked = [m for m in found if m.state in ("auto", "confirmed")]
    note = None
    if not posting.company:
        note = (
            "The posting does not name its company, so it could not be compared with fetched jobs."
        )
    elif not found:
        note = (
            "No matching posting was found among the jobs fetched from permitted sources. "
            "That does not mean it is not posted elsewhere."
        )
    return JobMatchesOut(
        note=note,
        sightings=[_yours(posting), *[public_sighting(j, s) for m in linked for j, s in m.members]],
        matches=[_match_out(m) for m in found],
    )


def matches(
    engine: Engine, settings: Settings, user_id: uuid.UUID, job_id: uuid.UUID
) -> JobMatchesOut:
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        return _view(db, posting, settings)


def decide(
    engine: Engine,
    settings: Settings,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    group_id: uuid.UUID,
    verb: str,
    ip_hash: str | None,
) -> JobMatchesOut:
    state = {"confirm": "confirmed", "undo": "undone", "reset": None}[verb]
    with tenant_session(engine, user_id) as db:
        posting = get_posting(db, user_id, job_id)
        if posting is None:
            raise not_found()
        if not decide_posting_link(
            db, user_id, posting, group_id, state, _today(), settings.source_review_window_days
        ):
            raise not_found()
        out = _view(db, posting, settings)
    record_audit(
        engine, category="audit", action="job.match_decided", actor_user_id=user_id,
        target_type="job_posting", target_id=str(job_id), ip_hash=ip_hash,
        metadata={"decision": verb},
    )  # fmt: skip
    return out


# ---- administrators


def _linked(job: SourceJob) -> LinkedJobOut:
    return LinkedJobOut(
        title=job.title,
        company_name=job.company_name,
        location=job.location,
        source_key=job.source_key,
        url=job.url,
    )


def admin_links(engine: Engine, state: str | None, limit: int) -> list[AdminLinkOut]:
    if state not in (None, "auto", "suggested", "confirmed", "undone"):
        raise ApiError(
            422, "VALIDATION_FAILED", "Some details need fixing.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"state": "Choose auto, suggested, confirmed or undone."},
        )  # fmt: skip
    with Session(engine) as db:
        return [
            AdminLinkOut(
                id=link.id, state=link.state, method=link.method, score=float(link.score),
                reason=link.reason, created_at=link.created_at, decided_at=link.decided_at,
                first=_linked(a), second=_linked(b),
            )
            for link, a, b in list_links(db, state, limit)
        ]  # fmt: skip


def admin_decide(
    engine: Engine, actor_id: uuid.UUID, link_id: uuid.UUID, verb: str, ip_hash: str | None
) -> AdminLinkOut:
    state = {"confirm": "confirmed", "undo": "undone"}[verb]
    with Session(engine) as db, db.begin():
        link = get_link(db, link_id)
        if link is None:
            raise not_found()
        set_link_state(db, link, state, actor_id)
        first, second = db.get(SourceJob, link.job_a), db.get(SourceJob, link.job_b)
        assert first is not None and second is not None  # noqa: S101 - foreign keys guarantee both
        out = AdminLinkOut(
            id=link.id, state=link.state, method=link.method, score=float(link.score),
            reason=link.reason, created_at=link.created_at, decided_at=link.decided_at,
            first=_linked(first), second=_linked(second),
        )  # fmt: skip
    record_audit(
        engine, category="audit", action=f"job_link.{state}", actor_user_id=actor_id,
        target_type="job_link", target_id=str(link_id), ip_hash=ip_hash,
    )  # fmt: skip
    return out
