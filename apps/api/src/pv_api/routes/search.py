"""Search planning and the source list. Every route needs a signed-in user.

Nothing here fetches jobs. The plan says what could be searched, what needs an import, and what is
unavailable and why. Sources and companies are shared reference data. Administrators change
sources through the admin routes, each change audited.
"""

from fastapi import APIRouter

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser
from pv_api.schemas import SearchPlanIn, SearchPlanOut, SourceOut
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
