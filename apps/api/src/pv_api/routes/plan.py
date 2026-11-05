"""Your plan and what you have used. Every route is scoped to the signed-in person.

Reading it is always allowed, whatever the quota says. Changing plan is not available yet: payments
exist only as an interface (pv_domain.billing) and answer that nothing is charged.
"""

from fastapi import APIRouter

from pv_api.deps import CurrentUser, EngineDep, SettingsDep, WriterUser
from pv_api.schemas import PlanOut, UpgradeIn
from pv_api.services import entitlement_service

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("", response_model=PlanOut)
def read(auth: CurrentUser, engine: EngineDep, settings: SettingsDep) -> PlanOut:
    return entitlement_service.view(engine, settings, auth.user_id)


@router.post("/upgrade", status_code=409)
def upgrade(body: UpgradeIn, auth: WriterUser) -> None:
    raise entitlement_service.upgrade_unavailable()
