"""Builds the status payload shared by /readyz and /api/v1/status."""

from fastapi import Request
from sqlalchemy.engine import Engine

from pv_api import __version__
from pv_api.schemas import Checks, StatusResponse
from pv_config import Settings
from pv_persistence.health import check_readiness


def build_status(request: Request) -> StatusResponse:
    engine: Engine = request.app.state.engine
    settings: Settings = request.app.state.settings
    report = check_readiness(engine)
    return StatusResponse(
        service="provenance-api",
        version=__version__,
        environment=settings.environment,
        ready=report.ready,
        checks=Checks(
            database="ok" if report.database else "fail",
            migrations=report.migrations,
        ),
    )
