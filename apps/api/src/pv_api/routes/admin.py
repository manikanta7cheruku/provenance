"""Administrative routes (ADR-0023).

Every route requires the ADMIN role, enforced on the server: non-admins get 404, as if the
area did not exist. Every mutation also needs the CSRF token and writes an audit event.
Admins see accounts, counters, queue state and audit records, never tenant data: Row Level
Security has no admin exception and these routes never query tenant tables.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from pv_api.deps import AdminUser, AdminWriter, EngineDep
from pv_api.schemas import (
    AdminOverview,
    AdminUserDetail,
    AdminUserList,
    AuditList,
    InviteCreate,
    InviteCreated,
    InviteOut,
    MessageResponse,
    SystemOverview,
)
from pv_api.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
def overview(_: AdminUser, engine: EngineDep) -> AdminOverview:
    users, verified, active = admin_service.overview_counts(engine)
    return AdminOverview(users=users, verified_users=verified, active_sessions=active)


@router.get("/system", response_model=SystemOverview)
def system(_: AdminUser, engine: EngineDep) -> SystemOverview:
    return admin_service.system_overview(engine)


@router.post("/tasks/{task_id}/requeue", response_model=MessageResponse)
def requeue_task(task_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.requeue_task(engine, actor, task_id)
    return MessageResponse(message="The task was queued again.")


# ---- users
@router.get("/users", response_model=AdminUserList)
def list_users(
    _: AdminUser,
    engine: EngineDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: Literal["USER", "ADMIN"] | None = None,
    status: Literal["active", "disabled"] | None = None,
    verified: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserList:
    return admin_service.list_users(
        engine, q=q, role=role, status=status, verified=verified, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: uuid.UUID, _: AdminUser, engine: EngineDep) -> AdminUserDetail:
    return admin_service.get_user_detail(engine, user_id)


@router.post("/users/{user_id}/disable", response_model=MessageResponse)
def disable_user(user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.set_user_active(engine, actor, user_id, active=False)
    return MessageResponse(message="The account is disabled and its sessions were ended.")


@router.post("/users/{user_id}/enable", response_model=MessageResponse)
def enable_user(user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.set_user_active(engine, actor, user_id, active=True)
    return MessageResponse(message="The account is enabled.")


@router.post("/users/{user_id}/revoke-sessions", response_model=MessageResponse)
def revoke_sessions(user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.revoke_user_sessions(engine, actor, user_id)
    return MessageResponse(message="All sessions for this account were ended.")


@router.post("/users/{user_id}/promote", response_model=MessageResponse)
def promote_user(user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.set_user_role(engine, actor, user_id, "ADMIN")
    return MessageResponse(message="The account is now an administrator.")


@router.post("/users/{user_id}/demote", response_model=MessageResponse)
def demote_user(user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.set_user_role(engine, actor, user_id, "USER")
    return MessageResponse(message="The account is no longer an administrator.")


@router.post("/users/{user_id}/resend-verification", response_model=MessageResponse)
def resend_verification(
    user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep
) -> MessageResponse:
    admin_service.resend_verification(engine, actor, user_id)
    return MessageResponse(message="A new confirmation email was queued.")


@router.post("/users/{user_id}/send-password-reset", response_model=MessageResponse)
def send_password_reset(
    user_id: uuid.UUID, actor: AdminWriter, engine: EngineDep
) -> MessageResponse:
    admin_service.send_password_reset(engine, actor, user_id)
    return MessageResponse(message="A password reset email was queued.")


# ---- invites
@router.get("/invites", response_model=list[InviteOut])
def list_invites(_: AdminUser, engine: EngineDep) -> list[InviteOut]:
    return admin_service.list_invites(engine)


@router.post("/invites", response_model=InviteCreated, status_code=201)
def create_invite(payload: InviteCreate, actor: AdminWriter, engine: EngineDep) -> InviteCreated:
    return admin_service.create_invite(engine, actor, email=payload.email, days=payload.days)


@router.post("/invites/{invite_id}/revoke", response_model=MessageResponse)
def revoke_invite(invite_id: uuid.UUID, actor: AdminWriter, engine: EngineDep) -> MessageResponse:
    admin_service.revoke_invite(engine, actor, invite_id)
    return MessageResponse(message="The invite was revoked.")


# ---- audit
@router.get("/audit", response_model=AuditList)
def audit(
    _: AdminUser,
    engine: EngineDep,
    category: Literal["audit", "security"] | None = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditList:
    return admin_service.list_audit(
        engine, category=category, action=action, before=before, limit=limit
    )
