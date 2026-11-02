"""Planning a search: read what the person asked for, then say plainly what can and cannot be done.

Nothing is fetched here. The plan is the honest answer to "where would this be searched?": which
sources may be searched, which need the person to import jobs, which are unavailable and why, and
which company each name resolved to. Sources and companies come from the registry. The model is
used once, to turn a typed sentence into a structure (class L). Everything after that is code.

Work authorization is read from the person's profile and shown as such. It is never taken from the
typed sentence.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.schemas import (
    AdminSourceOut,
    AuthorizationOut,
    CompanyCandidateOut,
    CompanyDecisionOut,
    FetchLogOut,
    PollQueuedOut,
    SearchPlanIn,
    SearchPlanOut,
    SourceDecisionOut,
    SourceJobOut,
    SourceOut,
    SourceUpdateIn,
)
from pv_api.services.job_service import not_found
from pv_config import Settings
from pv_domain.company import Candidate, Company
from pv_domain.failures import FailureClass
from pv_domain.job_feed import ADAPTERS
from pv_domain.resolver import SearchPlan, decide_source, plan_search
from pv_domain.search_intent import SearchIntent, clean_intent, clean_query, intent_to_dict
from pv_domain.sources import (
    SourceError,
    SourceRecord,
    enable_blocker,
    review_expired,
    unavailable_reason,
)
from pv_llm import LLMError, build_provider, content_hash, record_result
from pv_llm.search_intent import PROMPT_VERSION, parse_intent
from pv_persistence.audit import record_audit
from pv_persistence.jobs import load_seeker
from pv_persistence.models import JobSource
from pv_persistence.registry import (
    get_source_row,
    list_companies,
    list_source_rows,
    list_sources,
    to_record,
    update_source,
)
from pv_persistence.source_jobs import (
    queue_poll,
    recent_log,
    search_jobs,
    source_counts,
)
from pv_persistence.tenancy import tenant_session


def _today() -> date:
    return date.today()


def _candidate(c: Candidate) -> CompanyCandidateOut:
    return CompanyCandidateOut(
        key=c.company.key, name=c.company.canonical_name, score=round(c.score, 2)
    )


def _company(c: Company) -> CompanyCandidateOut:
    return CompanyCandidateOut(key=c.key, name=c.canonical_name, score=1.0)


def sources(engine: Engine, settings: Settings) -> list[SourceOut]:
    """Every source as the person sees it: what could be done with it right now."""
    with Session(engine) as db:
        rows = list_source_rows(db)
        counts = source_counts(db)
    out = []
    for row in rows:
        r = to_record(row)
        d = decide_source(r, SearchIntent(), _today(), settings.source_review_window_days)
        out.append(
            SourceOut(
                key=r.key,
                display_name=r.display_name,
                source_type=r.source_type.value,
                outcome=d.outcome.value,
                message=d.message,
                reason=d.reason,
                import_available=d.import_available,
                compliance_status=r.compliance_status.value,
                terms_checked_at=r.terms_checked_at,
                terms_url=r.terms_url,
                attribution_text=r.attribution_text,
                capabilities=dict(r.capabilities),
                health_status=row.health_status,
                last_success_at=row.last_success_at,
                jobs_open=counts.get(r.key, 0),
            )
        )
    return out


def _plan_out(plan: SearchPlan, how: str, authorization: AuthorizationOut) -> SearchPlanOut:
    return SearchPlanOut(
        interpreted_by=how,
        intent=intent_to_dict(plan.intent),
        headline=plan.headline,
        can_search_now=plan.can_search_now,
        notes=list(plan.notes),
        sources=[
            SourceDecisionOut(
                key=d.key,
                display_name=d.display_name,
                outcome=d.outcome.value,
                message=d.message,
                reason=d.reason,
                import_available=d.import_available,
                named_by_person=d.named_by_person,
                notes=list(d.notes),
            )
            for d in plan.sources
        ],
        companies=[
            CompanyDecisionOut(
                query=c.query,
                status=c.status.value,
                route=c.route.value,
                message=c.message,
                company=_company(c.company) if c.company else None,
                source_key=c.source_key,
                candidates=[_candidate(x) for x in c.candidates],
            )
            for c in plan.companies
        ],
        authorization=authorization,
    )


def _ai_error(code: str, message: str, status: int) -> ApiError:
    return ApiError(status, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


def plan(
    engine: Engine, settings: Settings, user_id: uuid.UUID, payload: SearchPlanIn
) -> SearchPlanOut:
    with Session(engine) as db:
        records = list_sources(db)
        companies = list_companies(db)
    with tenant_session(engine, user_id) as db:
        prefs, _ = load_seeker(db, user_id)
    authorization = AuthorizationOut(
        countries=list(prefs.authorized_countries),
        needs_sponsorship=prefs.needs_sponsorship,
        origin="your profile",
    )
    if payload.intent is not None and payload.query is None:
        intent = clean_intent(payload.intent)
        how = "the fields you set"
    else:
        query = clean_query(payload.query)
        if query is None:
            raise ApiError(
                422, "VALIDATION_FAILED", "Some details need fixing.",
                failure_class=FailureClass.VALIDATION_FAILED,
                fields={"query": "Describe the search in 1 to 500 characters."},
            )  # fmt: skip
        try:
            provider = build_provider(settings)
        except LLMError as exc:
            raise _ai_error(
                "AI_NOT_CONFIGURED",
                "Searching by sentence needs the AI service, which is not set up yet.",
                503,
            ) from exc
        keys = {r.key: r.display_name for r in records}
        try:
            intent, calls = parse_intent(
                provider, model=settings.llm_model, query=query, source_keys=keys
            )
        except LLMError as exc:
            record_result(
                engine, settings, provider=provider.name, model=settings.llm_model,
                purpose="search_intent", result=None, input_hash=content_hash(query),
                prompt_version=PROMPT_VERSION, user_id=user_id,
                error_class="LLM_RETRYABLE" if exc.retryable else "LLM_REJECTED",
            )  # fmt: skip
            raise _ai_error(
                "AI_UNAVAILABLE",
                "The AI service did not answer. Nothing was searched. Try again in a moment.",
                503,
            ) from exc
        for call in calls:
            record_result(
                engine, settings, provider=provider.name, model=settings.llm_model,
                purpose="search_intent", result=call, input_hash=content_hash(query),
                prompt_version=PROMPT_VERSION, user_id=user_id,
            )  # fmt: skip
        how = "the AI service"
    result = plan_search(intent, records, companies, _today(), settings.source_review_window_days)
    return _plan_out(result, how, authorization)


# ---- administrators


def _admin_out(row: JobSource, settings: Settings, jobs_open: int = 0) -> AdminSourceOut:
    record: SourceRecord = to_record(row)
    today = _today()
    window = settings.source_review_window_days
    return AdminSourceOut(
        key=row.key,
        display_name=row.display_name,
        source_type=row.source_type,
        adapter=row.adapter,
        endpoint_or_feed=row.endpoint_or_feed,
        capabilities=dict(row.capabilities),
        auth_requirements=row.auth_requirements,
        compliance_status=row.compliance_status,
        terms_checked_at=row.terms_checked_at,
        terms_url=row.terms_url,
        verification_owner=row.verification_owner,
        rate_limit=row.rate_limit,
        quota_policy=row.quota_policy,
        min_poll_interval_seconds=row.min_poll_interval_seconds,
        attribution_text=row.attribution_text,
        geographic_coverage=list(row.geographic_coverage),
        enabled=row.enabled,
        compliance_notes=row.compliance_notes,
        health_status=row.health_status,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
        failure_streak=row.failure_streak,
        review_expired=review_expired(row.terms_checked_at, today, window),
        enable_blocker=enable_blocker(record, today, window),
        edited=row.edited_at is not None,
        breaker_open_until=row.breaker_open_until,
        jobs_open=jobs_open,
    )


def admin_sources(engine: Engine, settings: Settings) -> list[AdminSourceOut]:
    with Session(engine) as db:
        counts = source_counts(db)
        return [_admin_out(r, settings, counts.get(r.key, 0)) for r in list_source_rows(db)]


def admin_update(
    engine: Engine,
    settings: Settings,
    actor_id: uuid.UUID,
    key: str,
    payload: SourceUpdateIn,
    ip_hash: str | None,
) -> AdminSourceOut:
    patch = payload.model_dump(exclude_unset=True)
    patch = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in patch.items()}
    with Session(engine) as db, db.begin():
        row = get_source_row(db, key)
        if row is None:
            raise not_found()
        was_enabled = row.enabled
        try:
            update_source(db, row, patch, _today(), settings.source_review_window_days)
        except SourceError as exc:
            raise ApiError(
                422, "VALIDATION_FAILED", "Some details need fixing.",
                failure_class=FailureClass.VALIDATION_FAILED, fields=exc.problems,
            ) from exc  # fmt: skip
        if row.enabled and not was_enabled and row.adapter in ADAPTERS:
            queue_poll(
                db,
                key,
                now=datetime.now(UTC),
                interval_seconds=row.min_poll_interval_seconds,
                chain=True,
            )
        out = _admin_out(row, settings, source_counts(db).get(key, 0))
    record_audit(
        engine, category="audit", action="source.updated", actor_user_id=actor_id,
        target_type="job_source", target_id=key, ip_hash=ip_hash,
        metadata={"fields": sorted(patch)},
    )  # fmt: skip
    return out


def request_poll(
    engine: Engine, settings: Settings, actor_id: uuid.UUID, key: str, ip_hash: str | None
) -> PollQueuedOut:
    """Ask for one poll now. The poll itself still refuses boards asked for too recently and a
    source that is not usable, so this cannot be used to get around the limits."""
    with Session(engine) as db, db.begin():
        row = get_source_row(db, key)
        if row is None:
            raise not_found()
        reason = unavailable_reason(to_record(row), _today(), settings.source_review_window_days)
        if reason is not None or row.adapter not in ADAPTERS:
            raise ApiError(
                409, "SOURCE_NOT_USABLE", "This source cannot be polled now.",
                failure_class=FailureClass.USER_ACTION_REQUIRED,
                fields={"source": reason or "It has no adapter."},
            )  # fmt: skip
        queued = queue_poll(db, key, now=datetime.now(UTC), interval_seconds=60, chain=False)
    record_audit(
        engine, category="audit", action="source.poll_requested", actor_user_id=actor_id,
        target_type="job_source", target_id=key, ip_hash=ip_hash,
    )  # fmt: skip
    return PollQueuedOut(
        message="A poll was queued. Boards asked for too recently are skipped."
        if queued
        else "A poll was already queued for this minute."
    )


def fetch_log(engine: Engine, key: str) -> list[FetchLogOut]:
    with Session(engine) as db:
        if get_source_row(db, key) is None:
            raise not_found()
        return [
            FetchLogOut(
                started_at=r.started_at, board_id=r.board_id, outcome=r.outcome,
                http_status=r.http_status, duration_ms=r.duration_ms, jobs_seen=r.jobs_seen,
                jobs_new=r.jobs_new, jobs_changed=r.jobs_changed, jobs_closed=r.jobs_closed,
                jobs_skipped=r.jobs_skipped, error_class=r.error_class,
            )
            for r in recent_log(db, key)
        ]  # fmt: skip


def _clean(items: list[str]) -> list[str]:
    return [s.strip()[:80] for s in items if s.strip()][:12]


def jobs(
    engine: Engine,
    settings: Settings,
    *,
    roles: list[str],
    companies: list[str],
    locations: list[str],
    work_mode: str | None,
    sources: list[str],
    limit: int,
    offset: int,
) -> list[SourceJobOut]:
    """Jobs fetched from sources that may be used right now, filtered in SQL."""
    with Session(engine) as db:
        rows = search_jobs(
            db,
            today=_today(),
            window_days=settings.source_review_window_days,
            roles=_clean(roles),
            companies=_clean(companies),
            locations=_clean(locations),
            work_mode=work_mode if work_mode in ("remote", "hybrid", "onsite") else None,
            sources=_clean(sources),
            limit=max(1, min(limit, 50)),
            offset=max(0, offset),
        )
        return [
            SourceJobOut(
                id=j.id, title=j.title, company_name=j.company_name, location=j.location,
                workplace=j.workplace, employment_type=j.employment_type, department=j.department,
                url=j.url, excerpt=j.description[:300], source_key=s.key,
                source_name=s.display_name, attribution_text=s.attribution_text,
                posted_at=j.posted_at, first_seen_at=j.first_seen_at,
            )
            for j, s in rows
        ]  # fmt: skip
