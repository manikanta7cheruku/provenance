"""Search planning and the source list. Every route needs a signed-in user.

Nothing here fetches jobs. The plan says what could be searched, what needs an import, and what is
unavailable and why. Sources and companies are shared reference data. Administrators change
sources through the admin routes, each change audited.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser
from pv_api.schemas import SearchPlanIn, SearchPlanOut, SourceJobOut, SourceOut
from pv_api.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/sources", response_model=list[SourceOut])
def sources(auth: CurrentUser, engine: EngineDep, settings: SettingsDep) -> list[SourceOut]:
    return search_service.sources(engine, settings)


@router.post("/plan", response_model=SearchPlanOut)
def plan(
    payload: SearchPlanIn,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> SearchPlanOut:
    limiter.check("search_plan_user", str(auth.user_id))
    return search_service.plan(engine, settings, auth.user_id, payload)


@router.get("/jobs", response_model=list[SourceJobOut])
def jobs(
    auth: CurrentUser,
    engine: EngineDep,
    settings: SettingsDep,
    roles: Annotated[list[str] | None, Query(max_length=12)] = None,
    companies: Annotated[list[str] | None, Query(max_length=12)] = None,
    locations: Annotated[list[str] | None, Query(max_length=12)] = None,
    sources: Annotated[list[str] | None, Query(max_length=12)] = None,
    work_mode: Annotated[str | None, Query(max_length=10)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> list[SourceJobOut]:
    return search_service.jobs(
        engine, settings, roles=roles or [], companies=companies or [], locations=locations or [],
        work_mode=work_mode, sources=sources or [], limit=limit, offset=offset,
    )  # fmt: skip
