"""Administrative routes. Operational aggregates only.

Admins do not get a bypass around tenant isolation: Row Level Security has no admin
exception, so an admin cannot read user profile data through the API or the database role.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pv_api.deps import AdminUser, EngineDep
from pv_api.schemas import AdminOverview
from pv_persistence.models import User, UserSession

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
def overview(_: AdminUser, engine: EngineDep) -> AdminOverview:
    with Session(engine) as db:
        users = db.execute(select(func.count()).select_from(User)).scalar_one()
        verified = db.execute(
            select(func.count()).select_from(User).where(User.email_verified_at.is_not(None))
        ).scalar_one()
        active = db.execute(
            select(func.count())
            .select_from(UserSession)
            .where(UserSession.revoked_at.is_(None), UserSession.expires_at > datetime.now(UTC))
        ).scalar_one()
    return AdminOverview(users=users, verified_users=verified, active_sessions=active)
