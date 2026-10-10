"""One error shape for the whole API.

Every error carries a machine code, a recoverability class and a message written for
the user. The frontend renders these directly. No raw exception text is ever returned.
"""

import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pv_domain.failures import FailureClass


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        failure_class: FailureClass,
        fields: dict[str, str] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.failure_class = failure_class
        self.fields = fields or {}
        self.retry_after_seconds = retry_after_seconds

    def body(self, request_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "failure_class": self.failure_class.value,
            "message": self.message,
            "request_id": request_id,
        }
        if self.fields:
            body["fields"] = self.fields
        if self.retry_after_seconds is not None:
            body["retry_after_seconds"] = self.retry_after_seconds
        return body


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", None) or uuid.uuid4().hex)


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        raise exc
    request_id = request_id_of(request)
    headers = {"X-Request-ID": request_id}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(status_code=exc.status_code, content=exc.body(request_id), headers=headers)


_FRIENDLY = {
    "missing": "This field is required.",
    "string_too_long": "This value is too long.",
    "string_too_short": "This value is too short.",
}


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [
            str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")
        ]
        name = location[-1] if location else "request"
        fields.setdefault(name, _FRIENDLY.get(str(error.get("type")), "Enter a valid value."))
    api_error = ApiError(
        422,
        "VALIDATION_FAILED",
        "Check the highlighted fields.",
        failure_class=FailureClass.VALIDATION_FAILED,
        fields=fields,
    )
    request_id = request_id_of(request)
    return JSONResponse(
        status_code=422, content=api_error.body(request_id), headers={"X-Request-ID": request_id}
    )
