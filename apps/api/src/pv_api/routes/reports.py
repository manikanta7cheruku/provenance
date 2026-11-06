"""Reports of a person's jobs as CSV, an Excel workbook or a Word document.

Every route is scoped to the signed-in user. Files are made by the worker and downloaded only by
their owner, only while they are ready and not expired. Anything else is "not found".
"""

import uuid

from fastapi import APIRouter, Request, Response

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import ReportIn, ReportOut
from pv_api.services import report_service
from pv_files import FileStorage

router = APIRouter(prefix="/reports", tags=["reports"])


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


@router.get("", response_model=list[ReportOut])
def reports(request: Request, auth: CurrentUser, engine: EngineDep) -> list[ReportOut]:
    return report_service.reports(engine, get_storage(request), auth.user_id)


@router.post("", response_model=ReportOut, status_code=202)
def create(
    payload: ReportIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ReportOut:
    limiter.check("report_export_user", str(auth.user_id))
    return report_service.create(
        engine, settings, get_storage(request), auth.user_id, payload, ip_hash_of(request, settings)
    )


@router.get("/{report_id}", response_model=ReportOut)
def one(report_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> ReportOut:
    return report_service.one(engine, auth.user_id, report_id)


@router.get("/{report_id}/download")
def download(
    report_id: uuid.UUID,
    request: Request,
    auth: CurrentUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> Response:
    limiter.check("report_download_user", str(auth.user_id))
    data, filename, media_type = report_service.download(
        engine, get_storage(request), auth.user_id, report_id
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{report_id}", status_code=204)
def delete(
    report_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
) -> Response:
    report_service.delete(
        engine, get_storage(request), auth.user_id, report_id, ip_hash_of(request, settings)
    )
    return Response(status_code=204)
