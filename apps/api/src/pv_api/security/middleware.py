"""HTTP security middleware: Origin check, body size limit, response headers."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from pv_api.http import client_ip
from pv_config import Settings
from pv_domain.auth import keyed_hash
from pv_domain.failures import FailureClass
from pv_domain.resume import MAX_UPLOAD_BYTES
from pv_persistence.audit import record_audit

CallNext = Callable[[Request], Awaitable[Response]]

MAX_BODY_BYTES = 1_048_576  # 1 MiB for ordinary JSON requests.
# The resume upload carries a file. The route also enforces the cap while reading the stream.
UPLOAD_PATH = "/api/v1/resume"
MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_BYTES + 16_384
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


async def origin_guard(request: Request, call_next: CallNext) -> Response:
    """Reject state-changing browser requests that come from another origin.

    Requests without an Origin header (scripts, tools) pass this check. They are still
    protected by the session cookie rules and the CSRF token on authenticated routes.
    """
    if request.method in _UNSAFE_METHODS:
        origin = request.headers.get("origin")
        settings: Settings = request.app.state.settings
        if origin is not None and origin not in settings.allowed_origins:
            engine: Engine = request.app.state.engine
            await run_in_threadpool(
                record_audit,
                engine,
                category="security",
                action="origin_rejected",
                ip_hash=keyed_hash(settings.secret_key.get_secret_value(), client_ip(request)),
                metadata={"path": request.url.path},
            )
            return JSONResponse(
                status_code=403,
                content={
                    "code": "ORIGIN_REJECTED",
                    "failure_class": FailureClass.SECURITY_REJECTED.value,
                    "message": (
                        "This request was blocked for your safety. Reload the page and try again."
                    ),
                },
            )
    return await call_next(request)


async def body_limit(request: Request, call_next: CallNext) -> Response:
    declared = request.headers.get("content-length")
    is_upload = request.method == "POST" and request.url.path == UPLOAD_PATH
    limit = MAX_UPLOAD_REQUEST_BYTES if is_upload else MAX_BODY_BYTES
    if declared is not None and declared.isdigit() and int(declared) > limit:
        return JSONResponse(
            status_code=413,
            content={
                "code": "PAYLOAD_TOO_LARGE",
                "failure_class": FailureClass.VALIDATION_FAILED.value,
                "message": "This request is too large.",
            },
        )
    return await call_next(request)


async def security_headers(request: Request, call_next: CallNext) -> Response:
    response = await call_next(request)
    settings: Settings = request.app.state.settings
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        # Private by default. A route that sends public, immutable files (the fonts) says so itself.
        response.headers["Cache-Control"] = "no-store"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response
