"""Career preparation for one job. Every route is scoped to the signed-in person and to a job they own.

The screen is built from one read (`GET`), and every change returns the whole preparation again so the
browser never has to guess what changed. Nothing here sends a message anywhere: a message is written
for the person, who copies it and sends it themselves.
"""

import uuid

from fastapi import APIRouter, Request

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import (
    MockAnswerIn,
    PreparationOut,
    PrepCompanyIn,
    PrepDateIn,
    PrepProgressIn,
    PrepTextIn,
)
from pv_api.services import preparation_service

router = APIRouter(prefix="/jobs", tags=["preparation"])


@router.get("/{job_id}/preparation", response_model=PreparationOut)
def read(job_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> PreparationOut:
    return preparation_service.view(engine, auth.user_id, job_id)


@router.post(
    "/{job_id}/preparation/outputs/{action}", response_model=PreparationOut, status_code=202
)
def write(
    job_id: uuid.UUID,
    action: str,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
    replace: bool = False,
) -> PreparationOut:
    limiter.check("prep_start_user", str(auth.user_id))
    return preparation_service.start_action(
        engine,
        auth.user_id,
        job_id,
        action,
        replace,
        ip_hash_of(request, settings),
        settings=settings,
    )


@router.put("/{job_id}/preparation/outputs/{action}", response_model=PreparationOut)
def edit(
    job_id: uuid.UUID,
    action: str,
    body: PrepTextIn,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.edit_text(engine, auth.user_id, job_id, action, body.text)


@router.put("/{job_id}/preparation/date", response_model=PreparationOut)
def date_(
    job_id: uuid.UUID, body: PrepDateIn, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.set_date(engine, auth.user_id, job_id, body.interview_date)


@router.put("/{job_id}/preparation/company", response_model=PreparationOut)
def company(
    job_id: uuid.UUID, body: PrepCompanyIn, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.set_company_notes(
        engine, auth.user_id, job_id, body.link, body.notes
    )


@router.put("/{job_id}/preparation/progress", response_model=PreparationOut)
def tick(
    job_id: uuid.UUID,
    body: PrepProgressIn,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.set_progress(engine, auth.user_id, job_id, body.key, body.done)


@router.post("/{job_id}/preparation/mock", response_model=PreparationOut, status_code=201)
def mock_start(
    job_id: uuid.UUID, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> PreparationOut:
    limiter.check("prep_start_user", str(auth.user_id))
    return preparation_service.mock_begin(engine, auth.user_id, job_id)


@router.post("/{job_id}/preparation/mock/{mock_id}/answer", response_model=PreparationOut)
def mock_answer(
    job_id: uuid.UUID,
    mock_id: uuid.UUID,
    body: MockAnswerIn,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.mock_answer(engine, auth.user_id, job_id, mock_id, body.answer)


@router.post("/{job_id}/preparation/mock/{mock_id}/finish", response_model=PreparationOut)
def mock_finish(
    job_id: uuid.UUID, mock_id: uuid.UUID, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> PreparationOut:
    limiter.check("prep_edit_user", str(auth.user_id))
    return preparation_service.mock_end(engine, auth.user_id, job_id, mock_id)
