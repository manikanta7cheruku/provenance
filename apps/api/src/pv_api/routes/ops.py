"""Operational probes. Not versioned and not part of the product API."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pv_api.status_service import build_status

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up. Never touches the database."""
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz(request: Request) -> JSONResponse:
    """Readiness: database reachable and migrations current."""
    status = build_status(request)
    return JSONResponse(
        status_code=200 if status.ready else 503,
        content=status.model_dump(mode="json"),
    )
