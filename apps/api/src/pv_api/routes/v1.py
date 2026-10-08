"""Product API, version 1."""

from fastapi import APIRouter, Request

from pv_api.schemas import StatusResponse
from pv_api.status_service import build_status

router = APIRouter(tags=["meta"])


@router.get("/status", response_model=StatusResponse)
def status(request: Request) -> StatusResponse:
    return build_status(request)
