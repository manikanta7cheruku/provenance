"""Request and response models. FastAPI turns these into the OpenAPI documentation."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Checks(BaseModel):
    database: Literal["ok", "fail"]
    migrations: Literal["ok", "behind", "unknown"]


class StatusResponse(BaseModel):
    service: str
    version: str
    environment: str
    ready: bool
    checks: Checks


# ---- authentication
class AuthConfig(BaseModel):
    signup_mode: Literal["invite", "open"]
    email_verification_required: bool


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["USER", "ADMIN"]
    email_verified: bool


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserOut | None
    csrf_token: str | None
    config: AuthConfig


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    invite_code: str | None = Field(default=None, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class TokenRequest(BaseModel):
    token: str = Field(max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class MessageResponse(BaseModel):
    message: str


# ---- profile entries (first tenant resource)
EntryType = Literal[
    "education", "work", "internship", "project", "skill", "certification", "achievement", "link"
]
_MAX_DATA_BYTES = 20_000


def _check_data_size(value: dict[str, Any]) -> dict[str, Any]:
    if len(json.dumps(value)) > _MAX_DATA_BYTES:
        raise ValueError("Entry data is too large.")
    return value


class ProfileEntryCreate(BaseModel):
    entry_type: EntryType
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def _validate_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_data_size(value)


class ProfileEntryUpdate(BaseModel):
    data: dict[str, Any]

    @field_validator("data")
    @classmethod
    def _validate_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_data_size(value)


class ProfileEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_type: str
    data: dict[str, Any]
    user_edited: bool
    created_at: datetime
    updated_at: datetime


# ---- admin
class AdminOverview(BaseModel):
    users: int
    verified_users: int
    active_sessions: int
