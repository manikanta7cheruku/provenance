"""Administrator operations.

Boundaries (ADR-0023):
- Admins see accounts, counters, queue state and audit records. They never see resumes,
  profile entries, evidence or jobs. Row Level Security has no admin exception, and this
  module never queries a tenant table. Per-user numbers come from user_stats.
- Every mutation writes an audit event naming the actor and the target.
- Two guards protect the system from lock-out: an admin cannot disable themselves, and the
  last active admin can be neither demoted nor disabled.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, ScalarSelect, func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, aliased

from pv_api.errors import ApiError
from pv_api.schemas import (
    AdminUserDetail,
    AdminUserList,
    AdminUserOut,
    AiModelUsage,
    AiUsage,
    AuditEventOut,
    AuditList,
    DeadLetterOut,
    InviteCreated,
    InviteOut,
    QueueSummary,
    SystemOverview,
    WorkerOut,
)
from pv_api.services.auth_service import AuthContext, issue_reset_email, issue_verification_email
from pv_api.services.auth_service import revoke_sessions as _revoke_sessions
from pv_domain.auth import generate_token, hash_token, is_valid_email, normalize_email
from pv_domain.failures import FailureClass
from pv_domain.tasks import NON_REQUEUEABLE
from pv_persistence.audit import record_audit
from pv_persistence.models import (
    AuditEvent,
    Invite,
    LlmCall,
    Task,
    User,
    UserSession,
    UserStats,
    WorkerHeartbeat,
)
from pv_persistence.queue import requeue_dead_letter

STALE_WORKER_SECONDS = 60
MAX_PAGE = 100


def _now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message, failure_class=FailureClass.USER_ACTION_REQUIRED)


# ---------------------------------------------------------------- users


def _session_subqueries() -> tuple[ScalarSelect[datetime], ScalarSelect[int]]:
    last_seen = (
        select(func.max(UserSession.last_seen_at))
        .where(UserSession.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    active = (
        select(func.count())
        .select_from(UserSession)
        .where(
            UserSession.user_id == User.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > func.now(),
        )
        .correlate(User)
        .scalar_subquery()
    )
    return last_seen, active


def _user_rows(db: Session, condition: ColumnElement[bool]) -> list[AdminUserOut]:
    last_seen, active = _session_subqueries()
    rows = db.execute(
        select(User, last_seen, active, UserStats.profile_entries_count, UserStats.runs_count)
        .outerjoin(UserStats, UserStats.user_id == User.id)
        .where(condition)
        .order_by(User.created_at.desc())
    ).all()
    return [_user_out(*row) for row in rows]


def _user_out(
    user: User,
    last_seen: datetime | None,
    active_sessions: int | None,
    entries: int | None,
    runs: int | None,
) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        role="ADMIN" if user.role == "ADMIN" else "USER",
        is_active=user.is_active,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
        last_seen_at=last_seen,
        active_sessions=active_sessions or 0,
        profile_entries_count=entries or 0,
        runs_count=runs or 0,
    )


def list_users(
    engine: Engine,
    *,
    q: str | None,
    role: Literal["USER", "ADMIN"] | None,
    status: Literal["active", "disabled"] | None,
    verified: bool | None,
    limit: int,
    offset: int,
) -> AdminUserList:
    limit = max(1, min(limit, MAX_PAGE))
    offset = max(0, offset)
    filters: list[ColumnElement[bool]] = []
    if q:
        filters.append(User.email.icontains(q.strip(), autoescape=True))
    if role:
        filters.append(User.role == role)
    if status:
        filters.append(User.is_active.is_(status == "active"))
    if verified is not None:
        filters.append(
            User.email_verified_at.is_not(None) if verified else User.email_verified_at.is_(None)
        )
    last_seen, active = _session_subqueries()
    with Session(engine) as db:
        total = db.execute(select(func.count()).select_from(User).where(*filters)).scalar_one()
        rows = db.execute(
            select(User, last_seen, active, UserStats.profile_entries_count, UserStats.runs_count)
            .outerjoin(UserStats, UserStats.user_id == User.id)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id)
            .limit(limit)
            .offset(offset)
        ).all()
    return AdminUserList(
        items=[_user_out(*row) for row in rows], total=total, limit=limit, offset=offset
    )


def _audit_out(event: AuditEvent, actor_email: str | None) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        category=event.category,
        action=event.action,
        actor_email=actor_email,
        target_type=event.target_type,
        target_id=event.target_id,
        created_at=event.created_at,
        details=event.event_metadata,
    )


def get_user_detail(engine: Engine, user_id: uuid.UUID) -> AdminUserDetail:
    with Session(engine) as db:
        rows = _user_rows(db, User.id == user_id)
        if not rows:
            raise _not_found()
        actor = aliased(User)
        events = db.execute(
            select(AuditEvent, actor.email)
            .outerjoin(actor, actor.id == AuditEvent.actor_user_id)
            .where(
                or_(
                    AuditEvent.actor_user_id == user_id,
                    (AuditEvent.target_type == "user") & (AuditEvent.target_id == str(user_id)),
                )
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(20)
        ).all()
    return AdminUserDetail(user=rows[0], recent_events=[_audit_out(e, a) for e, a in events])


def _load_target(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id, with_for_update=True)
    if user is None:
        raise _not_found()
    return user


def ensure_not_last_admin(db: Session, target: User) -> None:
    """Refuse to remove the only active administrator. Locks the admin rows while counting."""
    if target.role != "ADMIN" or not target.is_active:
        return
    admin_ids = (
        db.execute(
            select(User.id).where(User.role == "ADMIN", User.is_active.is_(True)).with_for_update()
        )
        .scalars()
        .all()
    )
    if len(admin_ids) <= 1:
        raise _conflict(
            "LAST_ADMIN",
            "This is the only active administrator. Promote another administrator first.",
        )


def _audit(engine: Engine, actor: AuthContext, action: str, target_id: uuid.UUID) -> None:
    record_audit(
        engine,
        category="audit",
        action=action,
        actor_user_id=actor.user_id,
        target_type="user",
        target_id=str(target_id),
    )


def set_user_active(
    engine: Engine, actor: AuthContext, user_id: uuid.UUID, *, active: bool
) -> None:
    with Session(engine) as db, db.begin():
        target = _load_target(db, user_id)
        if not active:
            if target.id == actor.user_id:
                raise _conflict("SELF_ACTION_FORBIDDEN", "You cannot disable your own account.")
            ensure_not_last_admin(db, target)
        target.is_active = active
        target.updated_at = _now()
        if not active:
            _revoke_sessions(db, target.id)
    _audit(engine, actor, "admin.user_disabled" if not active else "admin.user_enabled", user_id)


def revoke_user_sessions(engine: Engine, actor: AuthContext, user_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        target = _load_target(db, user_id)
        _revoke_sessions(db, target.id)
    _audit(engine, actor, "admin.sessions_revoked", user_id)


def set_user_role(
    engine: Engine, actor: AuthContext, user_id: uuid.UUID, role: Literal["USER", "ADMIN"]
) -> None:
    with Session(engine) as db, db.begin():
        target = _load_target(db, user_id)
        if target.role == role:
            raise _conflict("NO_CHANGE", f"This account already has the {role} role.")
        if role == "ADMIN" and not target.is_active:
            raise _conflict("USER_DISABLED", "Enable this account before promoting it.")
        if role == "USER":
            ensure_not_last_admin(db, target)
        target.role = role
        target.updated_at = _now()
    action = "admin.role_granted" if role == "ADMIN" else "admin.role_removed"
    _audit(engine, actor, action, user_id)


def resend_verification(engine: Engine, actor: AuthContext, user_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        target = _load_target(db, user_id)
        if target.email_verified_at is not None:
            raise _conflict("ALREADY_VERIFIED", "This email address is already confirmed.")
        if not target.is_active:
            raise _conflict("USER_DISABLED", "This account is disabled.")
        issue_verification_email(db, target.id, target.email)
    _audit(engine, actor, "admin.verification_resent", user_id)


def send_password_reset(engine: Engine, actor: AuthContext, user_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        target = _load_target(db, user_id)
        if not target.is_active:
            raise _conflict("USER_DISABLED", "This account is disabled.")
        issue_reset_email(db, target.id, target.email)
    _audit(engine, actor, "admin.password_reset_sent", user_id)


# ---------------------------------------------------------------- invites


def _invite_out(invite: Invite, creator_email: str | None) -> InviteOut:
    status: Literal["active", "used", "revoked", "expired"]
    if invite.used_at is not None:
        status = "used"
    elif invite.revoked_at is not None:
        status = "revoked"
    elif invite.expires_at <= _now():
        status = "expired"
    else:
        status = "active"
    return InviteOut(
        id=invite.id,
        email=invite.email,
        status=status,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        used_at=invite.used_at,
        revoked_at=invite.revoked_at,
        created_by_email=creator_email,
    )


def list_invites(engine: Engine) -> list[InviteOut]:
    creator = aliased(User)
    with Session(engine) as db:
        rows = db.execute(
            select(Invite, creator.email)
            .outerjoin(creator, creator.id == Invite.created_by)
            .order_by(Invite.created_at.desc())
            .limit(200)
        ).all()
    return [_invite_out(invite, email) for invite, email in rows]


def create_invite(
    engine: Engine, actor: AuthContext, *, email: str | None, days: int
) -> InviteCreated:
    bound = normalize_email(email) if email else None
    if bound is not None and not is_valid_email(bound):
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Check the highlighted fields.",
            failure_class=FailureClass.VALIDATION_FAILED,
            fields={"email": "Enter a valid email address."},
        )
    code = generate_token()
    with Session(engine, expire_on_commit=False) as db, db.begin():
        invite = Invite(
            code_hash=hash_token(code),
            email=bound,
            expires_at=_now() + timedelta(days=days),
            created_by=actor.user_id,
        )
        db.add(invite)
        db.flush()
        out = _invite_out(invite, actor.email)
    record_audit(
        engine,
        category="audit",
        action="admin.invite_created",
        actor_user_id=actor.user_id,
        target_type="invite",
        target_id=str(out.id),
        metadata={"bound": bound is not None, "days": days},
    )
    return InviteCreated(invite=out, code=code)


def revoke_invite(engine: Engine, actor: AuthContext, invite_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        invite = db.get(Invite, invite_id, with_for_update=True)
        if invite is None:
            raise _not_found()
        if invite.used_at is not None or invite.revoked_at is not None:
            raise _conflict("INVITE_NOT_ACTIVE", "This invite was already used or revoked.")
        invite.revoked_at = _now()
    record_audit(
        engine,
        category="audit",
        action="admin.invite_revoked",
        actor_user_id=actor.user_id,
        target_type="invite",
        target_id=str(invite_id),
    )


# ---------------------------------------------------------------- audit


def list_audit(
    engine: Engine,
    *,
    category: Literal["audit", "security"] | None,
    action: str | None,
    before: datetime | None,
    limit: int,
) -> AuditList:
    limit = max(1, min(limit, MAX_PAGE))
    actor = aliased(User)
    stmt = (
        select(AuditEvent, actor.email)
        .outerjoin(actor, actor.id == AuditEvent.actor_user_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
        .limit(limit + 1)
    )
    if category:
        stmt = stmt.where(AuditEvent.category == category)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action.strip(), autoescape=True))
    if before:
        stmt = stmt.where(AuditEvent.created_at < before)
    with Session(engine) as db:
        rows = db.execute(stmt).all()
    page = rows[:limit]
    next_before = page[-1][0].created_at if len(rows) > limit and page else None
    return AuditList(items=[_audit_out(e, a) for e, a in page], next_before=next_before)


# ---------------------------------------------------------------- system overview


def system_overview(engine: Engine) -> SystemOverview:
    now = _now()
    with Session(engine) as db:
        counts = {
            state: count
            for state, count in db.execute(
                select(Task.state, func.count()).group_by(Task.state)
            ).all()
        }
        oldest = db.execute(
            select(func.min(Task.run_after)).where(
                Task.state.in_(("queued", "retry_scheduled")), Task.run_after <= func.now()
            )
        ).scalar_one()
        heartbeats = (
            db.execute(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()))
            .scalars()
            .all()
        )
        dead = (
            db.execute(
                select(Task)
                .where(Task.state == "dead_letter")
                .order_by(Task.finished_at.desc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        since = now - timedelta(hours=24)
        totals = db.execute(
            select(
                func.count(),
                func.count().filter(LlmCall.status == "error"),
                func.coalesce(func.sum(LlmCall.input_tokens), 0),
                func.coalesce(func.sum(LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0),
            ).where(LlmCall.created_at >= since)
        ).one()
        per_model = db.execute(
            select(
                LlmCall.provider,
                LlmCall.model,
                func.count(),
                func.coalesce(func.sum(LlmCall.input_tokens), 0),
                func.coalesce(func.sum(LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0),
            )
            .where(LlmCall.created_at >= since)
            .group_by(LlmCall.provider, LlmCall.model)
            .order_by(func.count().desc())
        ).all()
    waiting_age = None if oldest is None else max(0, int((now - oldest).total_seconds()))
    return SystemOverview(
        queue=QueueSummary(by_state=counts, oldest_waiting_seconds=waiting_age),
        workers=[
            WorkerOut(
                worker_id=w.worker_id,
                hostname=w.hostname,
                started_at=w.started_at,
                last_seen_at=w.last_seen_at,
                tasks_processed=w.tasks_processed,
                status="alive"
                if (now - w.last_seen_at).total_seconds() < STALE_WORKER_SECONDS
                else "stale",
            )
            for w in heartbeats
        ],
        dead_letters=[
            DeadLetterOut(
                id=t.id,
                task_type=t.task_type,
                attempts=t.attempts,
                max_attempts=t.max_attempts,
                last_error=t.last_error,
                finished_at=t.finished_at,
                requeueable=t.task_type not in NON_REQUEUEABLE,
            )
            for t in dead
        ],
        ai_usage_24h=AiUsage(
            calls=totals[0],
            errors=totals[1],
            input_tokens=int(totals[2]),
            output_tokens=int(totals[3]),
            estimated_cost_usd=float(totals[4]),
            by_model=[
                AiModelUsage(
                    provider=row[0],
                    model=row[1],
                    calls=row[2],
                    input_tokens=int(row[3]),
                    output_tokens=int(row[4]),
                    estimated_cost_usd=float(row[5]),
                )
                for row in per_model
            ],
        ),
    )


def requeue_task(engine: Engine, actor: AuthContext, task_id: uuid.UUID) -> None:
    with Session(engine) as db, db.begin():
        task = db.get(Task, task_id, with_for_update=True)
        if task is None:
            raise _not_found()
        if task.state != "dead_letter":
            raise _conflict("NOT_DEAD_LETTER", "Only dead-lettered tasks can be requeued.")
        if task.task_type in NON_REQUEUEABLE:
            raise _conflict(
                "NOT_REQUEUEABLE",
                "This task carried a one-time link that was erased. "
                "Ask the user to request a new one.",
            )
        requeue_dead_letter(db, task_id)
    record_audit(
        engine,
        category="audit",
        action="admin.task_requeued",
        actor_user_id=actor.user_id,
        target_type="task",
        target_id=str(task_id),
    )


def overview_counts(engine: Engine) -> tuple[int, int, int]:
    with Session(engine) as db:
        users = db.execute(select(func.count()).select_from(User)).scalar_one()
        verified = db.execute(
            select(func.count()).select_from(User).where(User.email_verified_at.is_not(None))
        ).scalar_one()
        active = db.execute(
            select(func.count())
            .select_from(UserSession)
            .where(UserSession.revoked_at.is_(None), UserSession.expires_at > func.now())
        ).scalar_one()
    return users, verified, active
