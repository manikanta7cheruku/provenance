"""The resume studio. Every route is scoped to the signed-in user.

A resume is structured JSON, validated on every save and preview. The preview route returns the
same HTML the PDF is made from. PDFs are made by the worker and downloaded only by their owner.
"""

import uuid

from fastapi import APIRouter, Request, Response

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.errors import ApiError
from pv_api.schemas import (
    ExportOut,
    PreviewOut,
    RestoreIn,
    ResumeCreate,
    ResumeDocumentOut,
    ResumeDocumentSummaryOut,
    ResumePreview,
    ResumeSave,
    StudioOptionsOut,
    TemplateOut,
    VersionOut,
)
from pv_api.services import studio_service
from pv_domain.failures import FailureClass
from pv_domain.resume_doc import (
    DIVIDERS,
    FONT_PAIRS,
    MARGINS,
    PAPERS,
    SECTION_KINDS,
    SIZES,
    SPACINGS,
    TEMPLATE_INFO,
)
from pv_files import FileStorage, font_file

router = APIRouter(prefix="/studio", tags=["studio"])

_FONT_PAIR_LABELS = {
    "plex-newsreader": "Serif headings, sans body",
    "plex": "Sans serif throughout",
    "newsreader": "Serif throughout",
}


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


@router.get("/options", response_model=StudioOptionsOut)
def options(auth: CurrentUser, settings: SettingsDep) -> StudioOptionsOut:
    return StudioOptionsOut(
        templates=[
            TemplateOut(key=t.key, name=t.name, description=t.description, ats_safe=t.ats_safe)
            for t in TEMPLATE_INFO.values()
        ],
        font_pairs=[{"key": k, "label": _FONT_PAIR_LABELS[k]} for k in FONT_PAIRS],
        sizes=list(SIZES),
        spacings=list(SPACINGS),
        margins=list(MARGINS),
        dividers=list(DIVIDERS),
        papers=list(PAPERS),
        section_kinds=list(SECTION_KINDS),
        max_resumes=settings.studio_max_resumes,
    )


@router.get("/fonts/{name}")
def font(name: str) -> Response:
    """The shipped fonts, so the preview can load them. Public: they are open licence files."""
    path = font_file(name)
    if path is None:
        raise ApiError(404, "NOT_FOUND", "Not found.", failure_class=FailureClass.PERMANENT)
    return Response(
        content=path.read_bytes(),
        media_type="font/woff",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/resumes", response_model=list[ResumeDocumentSummaryOut])
def list_resumes(auth: CurrentUser, engine: EngineDep) -> list[ResumeDocumentSummaryOut]:
    return studio_service.list_resumes(engine, auth.user_id)


@router.post("/resumes", response_model=ResumeDocumentOut, status_code=201)
def create(
    payload: ResumeCreate,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
) -> ResumeDocumentOut:
    return studio_service.create(
        engine, settings, auth.user_id, payload, ip_hash_of(request, settings)
    )


@router.get("/resumes/{doc_id}", response_model=ResumeDocumentOut)
def get_resume(doc_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> ResumeDocumentOut:
    return studio_service.get(engine, auth.user_id, doc_id)


@router.put("/resumes/{doc_id}", response_model=ResumeDocumentSummaryOut)
def save(
    doc_id: uuid.UUID,
    payload: ResumeSave,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> ResumeDocumentSummaryOut:
    limiter.check("studio_save_user", str(auth.user_id))
    return studio_service.save(engine, auth.user_id, doc_id, payload)


@router.post("/resumes/{doc_id}/preview", response_model=PreviewOut)
def preview(
    doc_id: uuid.UUID,
    payload: ResumePreview,
    auth: WriterUser,
    engine: EngineDep,
    limiter: LimiterDep,
) -> PreviewOut:
    limiter.check("studio_preview_user", str(auth.user_id))
    return PreviewOut(html=studio_service.preview(engine, auth.user_id, doc_id, payload.content))


@router.get("/resumes/{doc_id}/versions", response_model=list[VersionOut])
def versions(doc_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> list[VersionOut]:
    return studio_service.versions(engine, auth.user_id, doc_id)


@router.post("/resumes/{doc_id}/versions/{version_id}/restore", response_model=ResumeDocumentOut)
def restore(
    doc_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: RestoreIn,
    auth: WriterUser,
    engine: EngineDep,
) -> ResumeDocumentOut:
    return studio_service.restore(engine, auth.user_id, doc_id, version_id, payload.revision)


@router.delete("/resumes/{doc_id}", status_code=204)
def delete(
    doc_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
) -> None:
    studio_service.remove(
        engine, get_storage(request), auth.user_id, doc_id, ip_hash_of(request, settings)
    )


@router.get("/resumes/{doc_id}/exports", response_model=list[ExportOut])
def exports(doc_id: uuid.UUID, auth: CurrentUser, engine: EngineDep) -> list[ExportOut]:
    return studio_service.exports(engine, auth.user_id, doc_id)


@router.post("/resumes/{doc_id}/exports", response_model=ExportOut, status_code=202)
def export(
    doc_id: uuid.UUID,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ExportOut:
    limiter.check("studio_export_user", str(auth.user_id))
    return studio_service.export(
        engine, settings, get_storage(request), auth.user_id, doc_id, ip_hash_of(request, settings)
    )


@router.get("/exports/{export_id}/download")
def download(
    export_id: uuid.UUID, request: Request, auth: CurrentUser, engine: EngineDep
) -> Response:
    data, filename = studio_service.download(engine, get_storage(request), auth.user_id, export_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
