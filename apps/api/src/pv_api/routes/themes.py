"""Saved themes for the resume studio. Every route is scoped to the signed-in user.

A theme is a font pair and four colors. Applying one is done in the browser by setting the resume's
style, which is checked again on save, so a theme can never put an unreadable color into a resume.
"""

import uuid

from fastapi import APIRouter, Request

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import ThemeIn, ThemeOut, ThemesOut
from pv_api.services import theme_service

router = APIRouter(prefix="/studio/themes", tags=["studio"])


@router.get("", response_model=ThemesOut)
def list_themes(auth: CurrentUser, engine: EngineDep) -> ThemesOut:
    return theme_service.list_all(engine, auth.user_id)


@router.post("", response_model=ThemeOut, status_code=201)
def create(
    body: ThemeIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ThemeOut:
    limiter.check("theme_write_user", str(auth.user_id))
    return theme_service.create(engine, auth.user_id, body, ip_hash_of(request, settings))


@router.put("/{theme_id}", response_model=ThemeOut)
def replace(
    theme_id: uuid.UUID,
    body: ThemeIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ThemeOut:
    limiter.check("theme_write_user", str(auth.user_id))
    return theme_service.replace(
        engine, auth.user_id, theme_id, body, ip_hash_of(request, settings)
    )


@router.delete("/{theme_id}", status_code=204)
def delete(
    theme_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> None:
    limiter.check("theme_write_user", str(auth.user_id))
    theme_service.remove(engine, auth.user_id, theme_id, ip_hash_of(request, settings))
