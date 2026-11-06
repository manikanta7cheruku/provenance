"""Your own data: a copy of it, and deleting the account.

Deleting is two steps, on purpose. This module takes the request: it checks the password and the
words typed, refuses to remove the only administrator, signs the person out everywhere, makes the
account inactive, and queues a durable task. The worker does the removal (stored files first, then
every row), so a crash half way is retried and finishes, and nothing depends on the browser staying
open. There is no undo once the task has run.
"""

import json

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.ratelimiter import RateLimiter
from pv_api.security.passwords import verify_password
from pv_api.services import auth_service
from pv_api.services.admin_service import ensure_not_last_admin
from pv_api.services.auth_service import AuthContext
from pv_domain.failures import FailureClass
from pv_domain.tasks import TASK_DELETE_ACCOUNT
from pv_persistence import account as account_store
from pv_persistence.audit import record_audit
from pv_persistence.models import User
from pv_persistence.queue import enqueue
from pv_persistence.tenancy import tenant_session

CONFIRM_PHRASE = "delete my account"


def _validation(fields: dict[str, str]) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_FAILED",
        "Some details need fixing.",
        failure_class=FailureClass.VALIDATION_FAILED,
        fields=fields,
    )


def export_json(
    engine: Engine, limiter: RateLimiter, context: AuthContext, ip_hash: str | None
) -> bytes:
    limiter.check("account_export_user", str(context.user_id))
    with tenant_session(engine, context.user_id) as db:
        user = db.get(User, context.user_id)
        if user is None:
            raise ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)
        data = account_store.export_data(db, user)
    record_audit(
        engine,
        category="audit",
        action="account.exported",
        actor_user_id=context.user_id,
        ip_hash=ip_hash,
    )
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def request_deletion(
    engine: Engine,
    limiter: RateLimiter,
    context: AuthContext,
    *,
    password: str,
    confirm: str,
    ip_hash: str | None,
) -> None:
    limiter.check("account_delete_user", str(context.user_id))
    if " ".join(confirm.lower().split()) != CONFIRM_PHRASE:
        raise _validation({"confirm": f'Type "{CONFIRM_PHRASE}" to confirm.'})
    with Session(engine, expire_on_commit=False) as db:
        user = db.get(User, context.user_id)
    if user is None or not verify_password(user.password_hash, password):
        record_audit(
            engine,
            category="security",
            action="account.deletion_password_failed",
            actor_user_id=context.user_id,
            ip_hash=ip_hash,
        )
        raise _validation({"password": "Your password is not correct."})
    with Session(engine, expire_on_commit=False) as db, db.begin():
        locked = db.get(User, context.user_id, with_for_update=True)
        if locked is None or locked.deletion_requested_at is not None:
            return  # already on its way: asking twice is harmless
        ensure_not_last_admin(db, locked)
        auth_service.revoke_sessions(db, context.user_id)
        deletion_id = account_store.request_deletion(db, context.user_id)
        enqueue(
            db,
            task_type=TASK_DELETE_ACCOUNT,
            idempotency_key=f"{TASK_DELETE_ACCOUNT}:{context.user_id}",
            payload={"args": {"user_id": str(context.user_id), "deletion_id": str(deletion_id)}},
            owner_user_id=None,  # the task must outlive the user row it deletes
            max_attempts=6,
        )
    record_audit(
        engine,
        category="audit",
        action="account.deletion_requested",
        actor_user_id=context.user_id,
        ip_hash=ip_hash,
    )


__all__ = ["CONFIRM_PHRASE", "export_json", "request_deletion"]
