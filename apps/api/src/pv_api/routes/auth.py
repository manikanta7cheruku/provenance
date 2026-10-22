"""Authentication routes. Thin: validation, cookies and responses only."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response

from pv_api.deps import (
    CsrfUser,
    EngineDep,
    LimiterDep,
    SettingsDep,
    ip_hash_of,
    optional_auth,
)
from pv_api.schemas import (
    AuthConfig,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenRequest,
    UserOut,
)
from pv_api.services import auth_service
from pv_api.services.auth_service import AuthContext
from pv_config import Settings
from pv_domain.auth import csrf_token_for
from pv_mail import delivery_hint

router = APIRouter(prefix="/auth", tags=["auth"])

OptionalUser = Annotated[AuthContext | None, Depends(optional_auth)]


def _config(settings: Settings) -> AuthConfig:
    return AuthConfig(
        signup_mode=settings.signup_mode,
        email_verification_required=settings.email_verification_required,
    )


def _session_response(context: AuthContext | None, settings: Settings) -> SessionResponse:
    if context is None:
        return SessionResponse(
            authenticated=False, user=None, csrf_token=None, config=_config(settings)
        )
    role: Literal["USER", "ADMIN"] = "ADMIN" if context.role == "ADMIN" else "USER"
    return SessionResponse(
        authenticated=True,
        user=UserOut(
            id=context.user_id,
            email=context.email,
            role=role,
            email_verified=context.email_verified,
        ),
        csrf_token=csrf_token_for(context.session_token, settings.secret_key.get_secret_value()),
        config=_config(settings),
    )


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.get("/session", response_model=SessionResponse)
def get_session(context: OptionalUser, settings: SettingsDep) -> SessionResponse:
    """Who am I? Anonymous callers get authenticated=false (not an error) plus the public config."""
    return _session_response(context, settings)


@router.post("/register", response_model=SessionResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> SessionResponse:
    ip_hash = ip_hash_of(request, settings)
    limiter.check("register_ip", ip_hash)
    result = auth_service.register(
        engine,
        settings,
        email=payload.email,
        password=payload.password,
        invite_code=payload.invite_code,
        ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, result.context.session_token, settings)
    return _session_response(result.context, settings)


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> SessionResponse:
    context = auth_service.login(
        engine,
        settings,
        limiter,
        email=payload.email,
        password=payload.password,
        ip_hash=ip_hash_of(request, settings),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, context.session_token, settings)
    return _session_response(context, settings)


@router.post("/logout", response_model=SessionResponse)
def logout(
    request: Request,
    response: Response,
    context: CsrfUser,
    settings: SettingsDep,
    engine: EngineDep,
) -> SessionResponse:
    auth_service.logout(engine, context, ip_hash_of(request, settings))
    _clear_session_cookie(response, settings)
    return _session_response(None, settings)


@router.post("/password/change", response_model=SessionResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    context: CsrfUser,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> SessionResponse:
    new_context = auth_service.change_password(
        engine,
        settings,
        limiter,
        context,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_hash=ip_hash_of(request, settings),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, new_context.session_token, settings)
    return _session_response(new_context, settings)


@router.post("/email/verify/request", response_model=MessageResponse)
def request_verification(
    context: CsrfUser,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> MessageResponse:
    if not auth_service.request_email_verification(engine, limiter, context):
        return MessageResponse(message="Your email is already confirmed.")
    hint = delivery_hint(settings)
    return MessageResponse(
        message=f"We queued a confirmation link for your email address. {hint.text}",
        delivery_hint=hint.mode,
    )


@router.post("/email/verify/confirm", response_model=MessageResponse)
def confirm_verification(
    payload: TokenRequest,
    request: Request,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> MessageResponse:
    auth_service.confirm_email(engine, limiter, payload.token, ip_hash_of(request, settings))
    return MessageResponse(message="Your email address is confirmed.")


@router.post("/password/forgot", response_model=MessageResponse, status_code=202)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> MessageResponse:
    """Always answers the same way, whether or not an account exists.

    The delivery hint depends only on configuration, so it cannot reveal which addresses exist.
    """
    auth_service.forgot_password(
        engine, settings, limiter, email=payload.email, ip_hash=ip_hash_of(request, settings)
    )
    hint = delivery_hint(settings)
    return MessageResponse(
        message=(
            "If an account exists for that address, we will send a link to reset the "
            f"password. {hint.text}"
        ),
        delivery_hint=hint.mode,
    )


@router.post("/password/reset", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
) -> MessageResponse:
    auth_service.reset_password(
        engine,
        limiter,
        token=payload.token,
        new_password=payload.new_password,
        ip_hash=ip_hash_of(request, settings),
    )
    return MessageResponse(message="Your password was changed. Sign in with the new password.")
