"""Application factory.

create_app() takes explicit settings so tests can build an app without touching
the environment. Settings are validated before anything else happens, so bad
configuration stops the process at startup instead of failing later.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pv_api import __version__
from pv_api.errors import ApiError, api_error_handler, validation_error_handler
from pv_api.logging_config import configure_logging
from pv_api.mail import Mailer, build_mailer
from pv_api.ratelimiter import RateLimiter
from pv_api.routes import admin, auth, ops, profile, v1
from pv_api.security.middleware import body_limit, origin_guard, security_headers
from pv_config import Settings, get_settings
from pv_domain.failures import FailureClass
from pv_domain.ratelimit import DEFAULT_POLICIES, RatePolicy
from pv_persistence.engine import create_db_engine

logger = logging.getLogger("pv_api")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
    response.headers["X-Request-ID"] = request_id
    return response


async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Never return a bare 500. Record the cause and give the user a request id."""
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "failure_class": FailureClass.INTERNAL_ERROR.value,
            "message": (
                "Something went wrong on our side. Your data is safe. "
                "Try again in a moment. If it keeps happening, quote the request id."
            ),
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


def create_app(
    settings: Settings | None = None,
    *,
    rate_policies: dict[str, RatePolicy] | None = None,
    mailer: Mailer | None = None,
) -> FastAPI:
    cfg = settings if settings is not None else get_settings()
    configure_logging(cfg.log_level)
    engine = create_db_engine(cfg.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("startup", extra={"path": cfg.environment})
        yield
        engine.dispose()
        logger.info("shutdown")

    production = cfg.environment == "production"
    app = FastAPI(
        title="Provenance API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if production else "/api/docs",
        redoc_url=None,
        openapi_url=None if production else "/api/openapi.json",
    )
    app.state.settings = cfg
    app.state.engine = engine
    app.state.limiter = RateLimiter(engine, rate_policies or DEFAULT_POLICIES)
    app.state.mailer = mailer if mailer is not None else build_mailer(cfg)

    if cfg.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )
    # Each registration wraps the previous ones, so the last is outermost.
    app.middleware("http")(origin_guard)
    app.middleware("http")(body_limit)
    app.middleware("http")(security_headers)
    app.middleware("http")(request_context)

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception)

    app.include_router(ops.router)
    app.include_router(v1.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(profile.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    return app
