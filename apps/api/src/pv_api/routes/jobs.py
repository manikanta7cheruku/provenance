"""Pasted job postings. Every route is scoped to the signed-in user.

A posting is private to the person who pasted it. The source name is a label they choose and the
acquisition method says how the text reached us (they pasted it), so the product never claims to
have searched a site the person copied from. Nothing here fetches a web address: a source link is
stored as text and shown as a link, and is never requested by the server.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Request, Response

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import (
    AnalysisOut,
    AnswerIn,
    DecisionIn,
    DecisionOut,
    DecisionResultOut,
    DraftEditIn,
    DraftOut,
    DraftsOut,
    DraftStartIn,
    FeedbackIn,
    JobCreate,
    JobCreatedOut,
    JobDetailOut,
    JobManualIn,
    JobMatchesOut,
    JobSummaryOut,
    NoteIn,
)
from pv_api.services import (
    analysis_service,
    dedupe_service,
    drafts_service,
    import_service,
    job_service,
    workbench_service,
)
from pv_domain.pipeline import Action

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreatedOut, status_code=201)
def paste(
    payload: JobCreate,
    request: Request,
    response: Response,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> JobCreatedOut:
    limiter.check("job_paste_user", str(auth.user_id))
    created = job_service.paste(
        engine, user_id=auth.user_id, payload=payload, ip_hash=ip_hash_of(request, settings)
    )
    if created.duplicate:
        response.status_code = 200  # the same posting again: nothing new was made
    return created


@router.post("/manual", response_model=JobCreatedOut, status_code=201)
def enter_manually(
    payload: JobManualIn,
    request: Request,
    response: Response,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> JobCreatedOut:
    limiter.check("job_manual_user", str(auth.user_id))
    created = import_service.manual(
        engine, user_id=auth.user_id, payload=payload, ip_hash=ip_hash_of(request, settings)
    )
    if created.duplicate:
        response.status_code = 200
    return created


@router.get("", response_model=list[JobSummaryOut])
def list_jobs(auth: CurrentUser, engine: EngineDep) -> list[JobSummaryOut]:
    return job_service.list_jobs(engine, auth.user_id)


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(job_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> JobDetailOut:
    return job_service.get_job(engine, auth.user_id, job_id)


@router.get("/{job_id}/matches", response_model=JobMatchesOut)
def job_matches(
    job_id: uuid.UUID, auth: CurrentUser, engine: EngineDep, settings: SettingsDep
) -> JobMatchesOut:
    return dedupe_service.matches(engine, settings, auth.user_id, job_id)


@router.post("/{job_id}/matches/{group_id}/{verb}", response_model=JobMatchesOut)
def decide_match(
    job_id: uuid.UUID,
    group_id: uuid.UUID,
    verb: Literal["confirm", "undo", "reset"],
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> JobMatchesOut:
    limiter.check("job_match_user", str(auth.user_id))
    return dedupe_service.decide(
        engine, settings, auth.user_id, job_id, group_id, verb, ip_hash_of(request, settings)
    )


@router.post("/{job_id}/decision", response_model=DecisionResultOut)
def decide(
    job_id: uuid.UUID,
    payload: DecisionIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> DecisionResultOut:
    limiter.check("decision_user", str(auth.user_id))
    return workbench_service.decide(
        engine,
        auth.user_id,
        job_id,
        Action(payload.action),
        payload.applied_on,
        ip_hash_of(request, settings),
    )


@router.put("/{job_id}/note", response_model=DecisionOut)
def save_note(
    job_id: uuid.UUID, payload: NoteIn, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> DecisionOut:
    limiter.check("decision_user", str(auth.user_id))
    return workbench_service.save_note(engine, auth.user_id, job_id, payload.note)


@router.get("/{job_id}/drafts", response_model=DraftsOut)
def get_drafts(job_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> DraftsOut:
    return drafts_service.view(engine, auth.user_id, job_id)


@router.post("/{job_id}/drafts", response_model=DraftsOut, status_code=202)
def start_draft(
    job_id: uuid.UUID,
    payload: DraftStartIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> DraftsOut:
    limiter.check("draft_start_user", str(auth.user_id))
    return drafts_service.start(
        engine, auth.user_id, job_id, payload, ip_hash_of(request, settings)
    )


@router.put("/{job_id}/drafts/{draft_id}", response_model=DraftOut)
def edit_draft(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: DraftEditIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> DraftOut:
    limiter.check("draft_edit_user", str(auth.user_id))
    return drafts_service.edit(
        engine, auth.user_id, job_id, draft_id, payload.body, ip_hash_of(request, settings)
    )


@router.delete("/{job_id}/drafts/{draft_id}", status_code=204)
def delete_draft(
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
) -> None:
    drafts_service.remove(engine, auth.user_id, job_id, draft_id, ip_hash_of(request, settings))


@router.post("/{job_id}/reanalyze", response_model=JobDetailOut)
def reanalyze(
    job_id: uuid.UUID, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> JobDetailOut:
    limiter.check("job_reanalyze_user", str(auth.user_id))
    return job_service.reanalyze(engine, auth.user_id, job_id)


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: uuid.UUID, request: Request, auth: WriterUser, engine: EngineDep, settings: SettingsDep
) -> None:
    job_service.delete_job(engine, auth.user_id, job_id, ip_hash_of(request, settings))


@router.get("/{job_id}/analysis", response_model=AnalysisOut)
def get_analysis(job_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> AnalysisOut:
    return analysis_service.get_view(engine, auth.user_id, job_id)


@router.post("/{job_id}/analysis", response_model=AnalysisOut)
def start_analysis(
    job_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> AnalysisOut:
    limiter.check("analysis_start_user", str(auth.user_id))
    return analysis_service.start(engine, auth.user_id, job_id, ip_hash_of(request, settings))


@router.post("/{job_id}/analysis/questions/{question_id}/answer", response_model=AnalysisOut)
def answer_question(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: AnswerIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> AnalysisOut:
    limiter.check("analysis_answer_user", str(auth.user_id))
    return analysis_service.answer(
        engine, auth.user_id, job_id, question_id, payload, ip_hash_of(request, settings)
    )


@router.post("/{job_id}/analysis/questions/{question_id}/skip", response_model=AnalysisOut)
def skip_question(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> AnalysisOut:
    limiter.check("analysis_answer_user", str(auth.user_id))
    return analysis_service.skip(engine, auth.user_id, job_id, question_id)


@router.post("/{job_id}/analysis/feedback", response_model=AnalysisOut)
def give_feedback(
    job_id: uuid.UUID,
    payload: FeedbackIn,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> AnalysisOut:
    limiter.check("analysis_feedback_user", str(auth.user_id))
    return analysis_service.give_feedback(engine, auth.user_id, job_id, payload)
