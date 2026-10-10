"""FastAPI dependencies: settings, database, identity, CSRF, roles.

Authorization decisions live here and in the services, not in route bodies.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.engine import Engine

from pv_api.errors import ApiError
from pv_api.http import client_ip
from pv_api.mail import Mailer
from pv_api.ratelimiter import RateLimiter
from pv_api.services.auth_service import AuthContext, resolve_session
from pv_config import Settings
from pv_domain.auth import csrf_token_for, keyed_hash, safe_equals
from pv_domain.failures import FailureClass
from pv_persistence.audit import record_audit


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def get_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.limiter
    return limiter


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
EngineDep = Annotated[Engine, Depends(get_engine)]
LimiterDep = Annotated[RateLimiter, Depends(get_limiter)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]


def ip_hash_of(request: Request, settings: Settings) -> str:
    return keyed_hash(settings.secret_key.get_secret_value(), client_ip(request))


def optional_auth(request: Request, settings: SettingsDep, engine: EngineDep) -> AuthContext | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return resolve_session(engine, settings, token)


def require_user(
    auth: Annotated[AuthContext | None, Depends(optional_auth)],
) -> AuthContext:
    if auth is None:
        raise ApiError(
            401,
            "UNAUTHENTICATED",
            "Sign in to continue.",
            failure_class=FailureClass.USER_ACTION_REQUIRED,
        )
    return auth


def require_csrf(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_user)],
    settings: SettingsDep,
    engine: EngineDep,
) -> AuthContext:
    """State-changing requests from a signed-in browser must carry the CSRF token."""
    expected = csrf_token_for(auth.session_token, settings.secret_key.get_secret_value())
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not safe_equals(supplied, expected):
        record_audit(
            engine,
            category="security",
            action="csrf_rejected",
            actor_user_id=auth.user_id,
            ip_hash=ip_hash_of(request, settings),
            metadata={"path": request.url.path},
        )
        raise ApiError(
            403,
            "CSRF_REJECTED",
            "This request was blocked for your safety. Reload the page and try again.",
            failure_class=FailureClass.SECURITY_REJECTED,
        )
    return auth


def require_verified_writer(
    auth: Annotated[AuthContext, Depends(require_csrf)],
    settings: SettingsDep,
) -> AuthContext:
    """Writes need a verified email when the deployment requires verification."""
    if settings.email_verification_required and not auth.email_verified:
        raise ApiError(
            403,
            "EMAIL_NOT_VERIFIED",
            "Confirm your email address to do this. Check your inbox for the link.",
            failure_class=FailureClass.USER_ACTION_REQUIRED,
        )
    return auth


def require_admin(auth: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    if auth.role != "ADMIN":
        # 404, not 403: do not reveal that the area exists.
        raise ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)
    return auth


CurrentUser = Annotated[AuthContext, Depends(require_user)]
CsrfUser = Annotated[AuthContext, Depends(require_csrf)]
WriterUser = Annotated[AuthContext, Depends(require_verified_writer)]
AdminUser = Annotated[AuthContext, Depends(require_admin)]
