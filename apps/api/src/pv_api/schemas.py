"""Response models. FastAPI turns these into the OpenAPI documentation."""

from typing import Literal

from pydantic import BaseModel


class Checks(BaseModel):
    database: Literal["ok", "fail"]
    migrations: Literal["ok", "behind", "unknown"]


class StatusResponse(BaseModel):
    service: str
    version: str
    environment: str
    ready: bool
    checks: Checks
