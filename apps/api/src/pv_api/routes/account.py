"""Download a copy of your data, or delete the account. Each route is for the signed-in person."""

from fastapi import APIRouter, Request, Response

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import DeleteAccountIn, MessageResponse
from pv_api.services import account_service

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
def export(
    request: Request,
    auth: CurrentUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> Response:
    data = account_service.export_json(engine, limiter, auth, ip_hash_of(request, settings))
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="Provenance data.json"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/delete", response_model=MessageResponse, status_code=202)
def delete(
    payload: DeleteAccountIn,
    request: Request,
    response: Response,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> MessageResponse:
    account_service.request_deletion(
        engine, limiter, auth, password=payload.password, confirm=payload.confirm,
        ip_hash=ip_hash_of(request, settings),
    )  # fmt: skip
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageResponse(
        message="Your account is being deleted and you are signed out. This can take a few minutes."
    )
