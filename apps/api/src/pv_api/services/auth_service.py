"""Authentication flows: registration, sessions, passwords, email tokens.

Rules that hold for every flow here:
- Tokens (session, verification, reset, invite) are stored only as hashes.
- Failures that could reveal whether an account exists use one message.
- Security-relevant events are written to the append-only audit log.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pv_api.errors import ApiError
from pv_api.ratelimiter import RateLimiter
from pv_api.security.passwords import (
    hash_password,
    needs_rehash,
    verify_dummy,
    verify_password,
)
from pv_config import Settings
from pv_domain.auth import (
    generate_token,
    hash_token,
    is_valid_email,
    keyed_hash,
    normalize_email,
    password_problems,
)
from pv_domain.failures import FailureClass
from pv_persistence.audit import record_audit
from pv_persistence.models import EmailToken, Invite, User, UserSession

SESSION_TOUCH_INTERVAL = timedelta(minutes=5)
VERIFY_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=1)


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    email: str
    role: str
    email_verified: bool
    session_id: uuid.UUID
    session_token: str


@dataclass(frozen=True)
class RegisterResult:
    context: AuthContext
    verification_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def _validation_error(fields: dict[str, str]) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_FAILED",
        "Check the highlighted fields.",
        failure_class=FailureClass.VALIDATION_FAILED,
        fields=fields,
    )


def _invite_invalid() -> ApiError:
    return ApiError(
        400,
        "INVITE_INVALID",
        "This invite code is not valid, has expired, or was already used.",
        failure_class=FailureClass.USER_ACTION_REQUIRED,
    )


def _token_invalid() -> ApiError:
    return ApiError(
        400,
        "TOKEN_INVALID",
        "This link is invalid or has expired. Request a new one.",
        failure_class=FailureClass.USER_ACTION_REQUIRED,
    )


def _create_session(
    db: Session, settings: Settings, user_id: uuid.UUID, user_agent: str | None
) -> tuple[uuid.UUID, str]:
    token = generate_token()
    session_row = UserSession(
        user_id=user_id,
        token_hash=hash_token(token),
        user_agent_hash=hash_token(user_agent) if user_agent else None,
        expires_at=_now() + timedelta(days=settings.session_max_days),
    )
    db.add(session_row)
    db.flush()
    return session_row.id, token


def _issue_email_token(db: Session, user_id: uuid.UUID, purpose: str, ttl: timedelta) -> str:
    """Create a single-use token. Older unused tokens of the same purpose stop working."""
    db.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user_id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=_now())
    )
    token = generate_token()
    db.add(
        EmailToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(token),
            expires_at=_now() + ttl,
        )
    )
    return token


def _consume_email_token(db: Session, token: str, purpose: str) -> uuid.UUID | None:
    """Atomically mark a valid token used. Returns the user id, or None if not valid."""
    row = db.execute(
        update(EmailToken)
        .where(
            EmailToken.token_hash == hash_token(token),
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > _now(),
        )
        .values(used_at=_now())
        .returning(EmailToken.user_id)
    ).first()
    return row[0] if row is not None else None


def _revoke_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def resolve_session(engine: Engine, settings: Settings, token: str) -> AuthContext | None:
    """Look up a session cookie value. Returns None when it is unknown, expired or revoked."""
    now = _now()
    idle_cutoff = now - timedelta(days=settings.session_idle_days)
    with Session(engine, expire_on_commit=False) as db:
        row = db.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(
                UserSession.token_hash == hash_token(token),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at >= idle_cutoff,
                User.is_active.is_(True),
            )
        ).first()
        if row is None:
            return None
        session_row, user = row
        if now - session_row.last_seen_at > SESSION_TOUCH_INTERVAL:
            session_row.last_seen_at = now
            db.commit()
        return AuthContext(
            user_id=user.id,
            email=user.email,
            role=user.role,
            email_verified=user.email_verified_at is not None,
            session_id=session_row.id,
            session_token=token,
        )


def register(
    engine: Engine,
    settings: Settings,
    *,
    email: str,
    password: str,
    invite_code: str | None,
    ip_hash: str,
    user_agent: str | None,
) -> RegisterResult:
    email = normalize_email(email)
    fields: dict[str, str] = {}
    if not is_valid_email(email):
        fields["email"] = "Enter a valid email address."
    problems = password_problems(password, email)
    if problems:
        fields["password"] = " ".join(problems)
    if fields:
        raise _validation_error(fields)

    password_hash = hash_password(password)  # slow on purpose, done before the transaction
    try:
        with Session(engine, expire_on_commit=False) as db, db.begin():
            invite: Invite | None = None
            if settings.signup_mode == "invite":
                if not invite_code:
                    raise _invite_invalid()
                invite = db.execute(
                    select(Invite)
                    .where(
                        Invite.code_hash == hash_token(invite_code.strip()),
                        Invite.used_at.is_(None),
                        Invite.expires_at > _now(),
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if invite is None or (
                    invite.email is not None and normalize_email(invite.email) != email
                ):
                    raise _invite_invalid()

            existing = db.execute(select(User.id).where(User.email == email)).first()
            if existing is not None:
                raise ApiError(
                    409,
                    "EMAIL_TAKEN",
                    "An account already exists for this email. Sign in instead.",
                    failure_class=FailureClass.USER_ACTION_REQUIRED,
                )

            user = User(email=email, password_hash=password_hash, role="USER")
            db.add(user)
            db.flush()
            if invite is not None:
                invite.used_at = _now()
                invite.used_by = user.id
            session_id, session_token = _create_session(db, settings, user.id, user_agent)
            verification_token = _issue_email_token(db, user.id, "verify", VERIFY_TOKEN_TTL)
            context = AuthContext(
                user_id=user.id,
                email=email,
                role="USER",
                email_verified=False,
                session_id=session_id,
                session_token=session_token,
            )
    except IntegrityError as exc:  # two registrations for one email raced
        raise ApiError(
            409,
            "EMAIL_TAKEN",
            "An account already exists for this email. Sign in instead.",
            failure_class=FailureClass.USER_ACTION_REQUIRED,
        ) from exc

    record_audit(
        engine,
        category="audit",
        action="auth.register",
        actor_user_id=context.user_id,
        ip_hash=ip_hash,
    )
    return RegisterResult(context=context, verification_token=verification_token)


def login(
    engine: Engine,
    settings: Settings,
    limiter: RateLimiter,
    *,
    email: str,
    password: str,
    ip_hash: str,
    user_agent: str | None,
) -> AuthContext:
    email = normalize_email(email)
    email_key = keyed_hash(settings.secret_key.get_secret_value(), email)
    limiter.check("login_ip", ip_hash)
    limiter.check("login_email", email_key)

    with Session(engine, expire_on_commit=False) as db:
        user = db.execute(
            select(User).where(User.email == email, User.is_active.is_(True))
        ).scalar_one_or_none()

    valid = (
        verify_password(user.password_hash, password)
        if user is not None
        else verify_dummy(password)
    )
    if user is None or not valid:
        record_audit(
            engine,
            category="security",
            action="auth.login_failed",
            ip_hash=ip_hash,
            metadata={"email_hash": email_key},
        )
        raise ApiError(
            401,
            "INVALID_CREDENTIALS",
            "Email or password is incorrect.",
            failure_class=FailureClass.USER_ACTION_REQUIRED,
        )

    with Session(engine, expire_on_commit=False) as db, db.begin():
        if needs_rehash(user.password_hash):
            db.execute(
                update(User).where(User.id == user.id).values(password_hash=hash_password(password))
            )
        session_id, session_token = _create_session(db, settings, user.id, user_agent)

    record_audit(
        engine, category="audit", action="auth.login", actor_user_id=user.id, ip_hash=ip_hash
    )
    return AuthContext(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        session_id=session_id,
        session_token=session_token,
    )


def logout(engine: Engine, context: AuthContext, ip_hash: str) -> None:
    with Session(engine) as db, db.begin():
        db.execute(
            update(UserSession)
            .where(UserSession.id == context.session_id)
            .values(revoked_at=_now())
        )
    record_audit(
        engine,
        category="audit",
        action="auth.logout",
        actor_user_id=context.user_id,
        ip_hash=ip_hash,
    )


def change_password(
    engine: Engine,
    settings: Settings,
    limiter: RateLimiter,
    context: AuthContext,
    *,
    current_password: str,
    new_password: str,
    ip_hash: str,
    user_agent: str | None,
) -> AuthContext:
    """Changes the password, revokes every session, and issues a fresh one (rotation)."""
    limiter.check("password_change_user", str(context.user_id))
    with Session(engine, expire_on_commit=False) as db:
        user = db.get(User, context.user_id)
    if user is None or not verify_password(user.password_hash, current_password):
        record_audit(
            engine,
            category="security",
            action="auth.password_change_failed",
            actor_user_id=context.user_id,
            ip_hash=ip_hash,
        )
        raise _validation_error({"current_password": "Your current password is not correct."})
    problems = password_problems(new_password, context.email)
    if new_password == current_password:
        problems.append("Choose a password you have not used before.")
    if problems:
        raise _validation_error({"new_password": " ".join(problems)})

    new_hash = hash_password(new_password)
    with Session(engine, expire_on_commit=False) as db, db.begin():
        db.execute(update(User).where(User.id == context.user_id).values(password_hash=new_hash))
        _revoke_sessions(db, context.user_id)
        session_id, session_token = _create_session(db, settings, context.user_id, user_agent)

    record_audit(
        engine,
        category="audit",
        action="auth.password_changed",
        actor_user_id=context.user_id,
        ip_hash=ip_hash,
    )
    return AuthContext(
        user_id=context.user_id,
        email=context.email,
        role=context.role,
        email_verified=context.email_verified,
        session_id=session_id,
        session_token=session_token,
    )


def request_email_verification(
    engine: Engine, limiter: RateLimiter, context: AuthContext
) -> str | None:
    """Returns a new verification token, or None when the email is already verified."""
    limiter.check("verify_request_user", str(context.user_id))
    if context.email_verified:
        return None
    with Session(engine) as db, db.begin():
        return _issue_email_token(db, context.user_id, "verify", VERIFY_TOKEN_TTL)


def confirm_email(engine: Engine, limiter: RateLimiter, token: str, ip_hash: str) -> None:
    limiter.check("verify_confirm_ip", ip_hash)
    with Session(engine) as db, db.begin():
        user_id = _consume_email_token(db, token, "verify")
        if user_id is None:
            raise _token_invalid()
        db.execute(
            update(User)
            .where(User.id == user_id, User.email_verified_at.is_(None))
            .values(email_verified_at=_now())
        )
    record_audit(
        engine,
        category="audit",
        action="auth.email_verified",
        actor_user_id=user_id,
        ip_hash=ip_hash,
    )


def forgot_password(
    engine: Engine,
    settings: Settings,
    limiter: RateLimiter,
    *,
    email: str,
    ip_hash: str,
) -> tuple[str, str] | None:
    """Returns (email, token) when an account exists. The caller answers identically either way."""
    email = normalize_email(email)
    email_key = keyed_hash(settings.secret_key.get_secret_value(), email)
    limiter.check("password_reset_ip", ip_hash)
    limiter.check("password_reset_email", email_key)
    with Session(engine) as db, db.begin():
        user = db.execute(
            select(User).where(User.email == email, User.is_active.is_(True))
        ).scalar_one_or_none()
        if user is None:
            result: tuple[str, str] | None = None
            user_id: uuid.UUID | None = None
        else:
            user_id = user.id
            result = (user.email, _issue_email_token(db, user.id, "reset", RESET_TOKEN_TTL))
    record_audit(
        engine,
        category="audit",
        action="auth.password_reset_requested",
        actor_user_id=user_id,
        ip_hash=ip_hash,
        metadata={"email_hash": email_key},
    )
    return result


def reset_password(
    engine: Engine,
    limiter: RateLimiter,
    *,
    token: str,
    new_password: str,
    ip_hash: str,
) -> None:
    limiter.check("reset_confirm_ip", ip_hash)
    with Session(engine, expire_on_commit=False) as db, db.begin():
        row = db.execute(
            select(EmailToken.user_id, User.email)
            .join(User, User.id == EmailToken.user_id)
            .where(
                EmailToken.token_hash == hash_token(token),
                EmailToken.purpose == "reset",
                EmailToken.used_at.is_(None),
                EmailToken.expires_at > _now(),
            )
        ).first()
        if row is None:
            raise _token_invalid()
        user_id, user_email = row
        problems = password_problems(new_password, user_email)
        if problems:  # raised before the token is consumed, so the link keeps working
            raise _validation_error({"new_password": " ".join(problems)})
        if _consume_email_token(db, token, "reset") is None:
            raise _token_invalid()
        db.execute(
            update(User).where(User.id == user_id).values(password_hash=hash_password(new_password))
        )
        _revoke_sessions(db, user_id)
    record_audit(
        engine,
        category="audit",
        action="auth.password_reset",
        actor_user_id=user_id,
        ip_hash=ip_hash,
    )
