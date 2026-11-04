"""The workbench: a person's list of jobs with filters, sorting and views, and bulk decisions.

Every route is scoped to the signed-in user. Which decisions are allowed is decided by the server
(pv_domain.pipeline); the browser shows what the server offers. Single decisions and notes are on
/jobs/{id}/decision and /jobs/{id}/note.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import BulkIn, BulkOut, ViewIn, ViewOut, WorkbenchOut
from pv_api.services import workbench_service
from pv_domain.pipeline import Action

router = APIRouter(prefix="/workbench", tags=["workbench"])

Many = Annotated[list[str] | None, Query(max_length=20)]


@router.get("", response_model=WorkbenchOut)
def list_jobs(
    auth: CurrentUser,
    engine: EngineDep,
    view: Annotated[str, Query(max_length=20)] = "active",
    q: Annotated[str, Query(max_length=200)] = "",
    state: Many = None,
    eligibility: Many = None,
    band: Many = None,
    work_mode: Many = None,
    employment_type: Many = None,
    seniority: Many = None,
    source: Many = None,
    company: Annotated[str, Query(max_length=200)] = "",
    location: Annotated[str, Query(max_length=200)] = "",
    sort: Annotated[str, Query(max_length=20)] = "added",
    desc: Annotated[bool | None, Query()] = None,
) -> WorkbenchOut:
    raw: dict[str, object] = {
        "view": view,
        "text": q,
        "states": state or [],
        "eligibility": eligibility or [],
        "bands": band or [],
        "work_modes": work_mode or [],
        "employment_types": employment_type or [],
        "seniorities": seniority or [],
        "sources": source or [],
        "company": company,
        "location": location,
        "sort": sort,
        "descending": desc,
    }
    return workbench_service.workbench(engine, auth.user_id, raw)


@router.post("/bulk", response_model=BulkOut)
def bulk(
    payload: BulkIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> BulkOut:
    limiter.check("decision_bulk_user", str(auth.user_id))
    return workbench_service.bulk(
        engine, auth.user_id, payload.ids, Action(payload.action), ip_hash_of(request, settings)
    )


@router.get("/views", response_model=list[ViewOut])
def list_views(auth: CurrentUser, engine: EngineDep) -> list[ViewOut]:
    return workbench_service.views(engine, auth.user_id)


@router.post("/views", response_model=ViewOut, status_code=201)
def save_view(payload: ViewIn, auth: WriterUser, engine: EngineDep, limiter: LimiterDep) -> ViewOut:
    limiter.check("workbench_view_user", str(auth.user_id))
    return workbench_service.save_view(engine, auth.user_id, payload)


@router.delete("/views/{view_id}", status_code=204)
def delete_view(
    view_id: uuid.UUID, auth: WriterUser, engine: EngineDep, limiter: LimiterDep
) -> None:
    limiter.check("workbench_view_user", str(auth.user_id))
    workbench_service.delete_view(engine, auth.user_id, view_id)
