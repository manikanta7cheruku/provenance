"""Authentication routes. Thin: validation, cookies and responses only."""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from pv_api.deps import (
    CsrfUser,
    EngineDep,
    LimiterDep,
    MailerDep,
    SettingsDep,
    ip_hash_of,
    optional_auth,
)
from pv_api.mail import send_reset_email, send_verification_email
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
    background: BackgroundTasks,
    settings: SettingsDep,
    engine: EngineDep,
    limiter: LimiterDep,
    mailer: MailerDep,
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
    background.add_task(
        send_verification_email, mailer, settings, result.context.email, result.verification_token
    )
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
    mailer: MailerDep,
    background: BackgroundTasks,
) -> MessageResponse:
    token = auth_service.request_email_verification(engine, limiter, context)
    if token is None:
        return MessageResponse(message="Your email is already confirmed.")
    background.add_task(send_verification_email, mailer, settings, context.email, token)
    return MessageResponse(message="We sent a confirmation link to your email address.")


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
    mailer: MailerDep,
    background: BackgroundTasks,
) -> MessageResponse:
    """Always answers the same way, whether or not an account exists."""
    result = auth_service.forgot_password(
        engine, settings, limiter, email=payload.email, ip_hash=ip_hash_of(request, settings)
    )
    if result is not None:
        email, token = result
        background.add_task(send_reset_email, mailer, settings, email, token)
    return MessageResponse(
        message="If an account exists for that address, we sent a link to reset the password."
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
