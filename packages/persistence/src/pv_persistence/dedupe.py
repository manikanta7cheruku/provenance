"""Duplicate detection in the database: links between fetched jobs, groups, and a person decisions.

Two sides, kept apart on purpose:

  Public side. Fetched jobs are shared reference data. Code compares each new or changed job with the
  other jobs of the same company (pv_domain.dedupe) and stores an edge. Auto and confirmed edges
  join jobs into a group (`group_id`, the smallest id in the connected set). An administrator can
  confirm a suggested edge or undo any edge. Undoing removes the edge from the group and the group
  is worked out again, so it splits exactly where that link was the only join. An undone edge is
  never made again by code, because the edge row stays and code only creates missing edges.

  Private side. A posting a person pasted belongs to them (Row Level Security). It is compared with
  public jobs when it is read, and only the person decisions (same job, or not the same job) are
  stored, in posting_links. Public jobs never learn that a private posting exists, and one person
  decision never affects anyone else.

Call inside a plain session for the public side and inside tenant_session for the private side.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pv_domain.dedupe import (
    JobFacts,
    Level,
    Match,
    compare,
    components,
    normalize_company,
    ordered_pair,
)
from pv_persistence.models import JobPosting, JobSource, PostingLink, SourceJob, SourceJobLink
from pv_persistence.source_jobs import usable_where

ACTIVE = ("auto", "confirmed")
MAX_CANDIDATES = 400


def job_facts(job: SourceJob) -> JobFacts:
    return JobFacts(
        url=job.url,
        company=job.company_name,
        title=job.title,
        location=job.location,
        description=job.description,
        source_key=job.source_key,
        board_id=job.board_id,
        external_id=job.external_id,
        content_hash=job.content_hash,
    )


def posting_facts(posting: JobPosting) -> JobFacts:
    place = posting.facts.get("location") if isinstance(posting.facts, dict) else None
    location = (
        place.get("value")
        if isinstance(place, dict) and isinstance(place.get("value"), str)
        else ""
    )
    return JobFacts(
        url=posting.source_url,
        company=posting.company,
        title=posting.title or "",
        location=str(location or ""),
        description=posting.raw_text,
    )


# ---- public side


@dataclass(frozen=True)
class LinkCounts:
    auto: int
    suggested: int


def link_jobs(db: Session, job_ids: tuple[uuid.UUID, ...] | list[uuid.UUID]) -> LinkCounts:
    """Compare each job with the other jobs of its company and store the edges that are missing.

    An edge that already exists in any state is left alone: a decision is never overridden."""
    auto = suggested = 0
    touched: set[uuid.UUID] = set()
    for job in db.execute(select(SourceJob).where(SourceJob.id.in_(list(job_ids)))).scalars():
        if not job.company_norm:
            continue
        candidates = list(
            db.execute(
                select(SourceJob)
                .where(SourceJob.company_norm == job.company_norm, SourceJob.id != job.id)
                .limit(MAX_CANDIDATES)
            ).scalars()
        )
        if not candidates:
            continue
        mine = job_facts(job)
        known = {
            (link.job_a, link.job_b)
            for link in db.execute(
                select(SourceJobLink).where(
                    SourceJobLink.job_a.in_([job.id, *[c.id for c in candidates]]),
                    SourceJobLink.job_b.in_([job.id, *[c.id for c in candidates]]),
                )
            ).scalars()
        }
        for other in candidates:
            a, b = ordered_pair(str(job.id), str(other.id))
            pair = (uuid.UUID(a), uuid.UUID(b))
            if pair in known:
                continue
            match = compare(mine, job_facts(other))
            if match is None:
                continue
            state = "auto" if match.level == Level.AUTO else "suggested"
            db.add(
                SourceJobLink(
                    job_a=pair[0],
                    job_b=pair[1],
                    method=match.method,
                    score=match.score,
                    reason=match.reason,
                    state=state,
                )
            )
            known.add(pair)
            auto += state == "auto"
            suggested += state == "suggested"
            touched.update(pair)
    db.flush()
    if touched or job_ids:
        regroup(db, set(touched) | set(job_ids))
    return LinkCounts(auto, suggested)


def regroup(db: Session, ids: set[uuid.UUID]) -> None:
    """Work out the groups again for every job connected to these, from the active edges."""
    nodes = set(ids)
    while True:
        edges = list(
            db.execute(
                select(SourceJobLink).where(
                    SourceJobLink.state.in_(ACTIVE),
                    SourceJobLink.job_a.in_(nodes) | SourceJobLink.job_b.in_(nodes),
                )
            ).scalars()
        )
        grown = nodes | {e.job_a for e in edges} | {e.job_b for e in edges}
        if grown == nodes:
            break
        nodes = grown
    groups = components([str(n) for n in nodes], [(str(e.job_a), str(e.job_b)) for e in edges])
    for job in db.execute(select(SourceJob).where(SourceJob.id.in_(nodes))).scalars():
        job.group_id = uuid.UUID(groups[str(job.id)])
    db.flush()


def get_link(db: Session, link_id: uuid.UUID) -> SourceJobLink | None:
    return db.get(SourceJobLink, link_id)


def set_link_state(db: Session, link: SourceJobLink, state: str, actor: uuid.UUID) -> None:
    """Confirm or undo an edge, then work the groups out again. Undoing can split a group."""
    link.state = state
    link.decided_at = datetime.now(UTC)
    link.decided_by = actor
    db.flush()
    regroup(db, {link.job_a, link.job_b})


def list_links(
    db: Session, state: str | None, limit: int
) -> list[tuple[SourceJobLink, SourceJob, SourceJob]]:
    stmt = select(SourceJobLink).order_by(SourceJobLink.created_at.desc()).limit(min(limit, 100))
    if state:
        stmt = stmt.where(SourceJobLink.state == state)
    out = []
    for link in db.execute(stmt).scalars():
        first, second = db.get(SourceJob, link.job_a), db.get(SourceJob, link.job_b)
        if first is not None and second is not None:
            out.append((link, first, second))
    return out


# ---- private side


@dataclass(frozen=True)
class PostingMatch:
    group_id: uuid.UUID
    job: SourceJob  # the job shown for the group
    source: JobSource
    match: Match
    state: str  # auto, suggested, confirmed or undone
    members: tuple[tuple[SourceJob, JobSource], ...]


def posting_matches(
    db: Session, posting: JobPosting, today: date, window_days: int
) -> list[PostingMatch]:
    """Public jobs that may be the posting a person pasted, with the decisions they made.

    Computed when read, so a job fetched after the paste is found, and nothing goes stale. Only jobs
    from sources that may be used right now are considered."""
    company = normalize_company(posting.company)
    if not company:
        return []
    candidates = list(
        db.execute(
            select(SourceJob, JobSource)
            .join(JobSource, JobSource.key == SourceJob.source_key)
            .where(SourceJob.company_norm == company, *usable_where(today, window_days))
            .limit(MAX_CANDIDATES)
        ).all()
    )
    mine = posting_facts(posting)
    best: dict[uuid.UUID, tuple[Match, SourceJob, JobSource]] = {}
    members: dict[uuid.UUID, list[tuple[SourceJob, JobSource]]] = {}
    for job, source in candidates:
        group = job.group_id or job.id
        members.setdefault(group, []).append((job, source))
        match = compare(mine, job_facts(job))
        if match is None:
            continue
        current = best.get(group)
        if current is None or match.score > current[0].score:
            best[group] = (match, job, source)
    decisions = {
        link.source_job_id: link.state
        for link in db.execute(
            select(PostingLink).where(PostingLink.posting_id == posting.id)
        ).scalars()
    }
    group_of: dict[uuid.UUID, uuid.UUID] = {
        job.id: (job.group_id or job.id) for job, _ in candidates
    }
    by_group: dict[uuid.UUID, str] = {}
    for job_id, state in decisions.items():
        found = group_of.get(job_id)
        if found is not None:
            by_group[found] = state
    out = []
    for group, (match, job, source) in best.items():
        state = by_group.get(group, match.level.value)
        out.append(PostingMatch(group, job, source, match, state, tuple(members[group])))
    out.sort(key=lambda m: (-m.match.score, str(m.group_id)))
    return out


def decide_posting_link(
    db: Session, owner: uuid.UUID, posting: JobPosting, group_id: uuid.UUID, state: str | None,
    today: date, window_days: int,
) -> bool:  # fmt: skip
    """Record the person decision for a group of public jobs, or clear it (state None).

    The group must be one this posting is a candidate for. Returns False when it is not."""
    wanted = [m for m in posting_matches(db, posting, today, window_days) if m.group_id == group_id]
    if not wanted:
        return False
    ids = [job.id for job, _ in wanted[0].members]
    rows = db.execute(
        select(PostingLink).where(
            PostingLink.posting_id == posting.id, PostingLink.source_job_id.in_(ids)
        )
    ).scalars()
    for row in list(rows):
        db.delete(row)
    db.flush()
    if state is not None:
        db.add(
            PostingLink(
                owner_user_id=owner,
                posting_id=posting.id,
                source_job_id=wanted[0].job.id,
                state=state,
            )
        )
    db.flush()
    return True


def count_links(db: Session) -> dict[str, int]:
    rows = db.execute(select(SourceJobLink.state, func.count()).group_by(SourceJobLink.state)).all()
    return {state: int(n) for state, n in rows}
