"""The shortlist email. Every route is scoped to the signed-in user.

The email is off until the person turns it on, and goes only to a verified address. These routes
queue work and read settings. The worker sends the email.
"""

from fastapi import APIRouter, Request

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import (
    ShortlistOut,
    ShortlistPreviewOut,
    ShortlistSendOut,
    ShortlistSettingsIn,
)
from pv_api.services import shortlist_service

router = APIRouter(prefix="/shortlist", tags=["shortlist"])


@router.get("", response_model=ShortlistOut)
def get_shortlist(auth: CurrentUser, engine: EngineDep, settings: SettingsDep) -> ShortlistOut:
    return shortlist_service.view(engine, settings, auth.user_id)


@router.put("", response_model=ShortlistOut)
def save_shortlist(
    payload: ShortlistSettingsIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ShortlistOut:
    limiter.check("shortlist_settings_user", str(auth.user_id))
    return shortlist_service.save(
        engine, settings, auth.user_id, payload, ip_hash_of(request, settings)
    )


@router.get("/preview", response_model=ShortlistPreviewOut)
def preview(auth: CurrentUser, engine: EngineDep) -> ShortlistPreviewOut:
    return shortlist_service.preview(engine, auth.user_id)


@router.post("/send", response_model=ShortlistSendOut, status_code=202)
def send_now(
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ShortlistSendOut:
    limiter.check("shortlist_send_user", str(auth.user_id))
    return shortlist_service.send_now(engine, auth.user_id, ip_hash_of(request, settings))
