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
    # Set when the message is about email: "log", "smtp_dev" or "smtp" (what really happens).
    delivery_hint: str | None = None


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


# ---- admin: overview counters (unchanged from checkpoint 1.2)
class AdminOverview(BaseModel):
    users: int
    verified_users: int
    active_sessions: int


# ---- admin: users
class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["USER", "ADMIN"]
    is_active: bool
    email_verified: bool
    created_at: datetime
    last_seen_at: datetime | None
    active_sessions: int
    # Counters only. Administrators never see resumes, entries, evidence or jobs.
    profile_entries_count: int
    runs_count: int


class AdminUserList(BaseModel):
    items: list[AdminUserOut]
    total: int
    limit: int
    offset: int


class AuditEventOut(BaseModel):
    id: uuid.UUID
    category: str
    action: str
    actor_email: str | None
    target_type: str | None
    target_id: str | None
    created_at: datetime
    details: dict[str, Any]


class AdminUserDetail(BaseModel):
    user: AdminUserOut
    recent_events: list[AuditEventOut]


class AuditList(BaseModel):
    items: list[AuditEventOut]
    next_before: datetime | None


# ---- admin: invites
class InviteOut(BaseModel):
    id: uuid.UUID
    email: str | None
    status: Literal["active", "used", "revoked", "expired"]
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    created_by_email: str | None


class InviteCreate(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    days: int = Field(default=7, ge=1, le=30)


class InviteCreated(BaseModel):
    invite: InviteOut
    code: str  # shown once; only its hash is stored


# ---- admin: system overview
class QueueSummary(BaseModel):
    by_state: dict[str, int]
    oldest_waiting_seconds: int | None


class WorkerOut(BaseModel):
    worker_id: str
    hostname: str
    started_at: datetime
    last_seen_at: datetime
    tasks_processed: int
    status: Literal["alive", "stale"]


class DeadLetterOut(BaseModel):
    id: uuid.UUID
    task_type: str
    attempts: int
    max_attempts: int
    last_error: str | None
    finished_at: datetime | None
    requeueable: bool


class AiModelUsage(BaseModel):
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class AiUsage(BaseModel):
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    by_model: list[AiModelUsage]


class SystemOverview(BaseModel):
    queue: QueueSummary
    workers: list[WorkerOut]
    dead_letters: list[DeadLetterOut]
    ai_usage_24h: AiUsage


# ---- runs (user-facing)
UiStateName = Literal[
    "queued",
    "processing",
    "waiting_for_you",
    "retrying",
    "completed",
    "retry_available",
    "permanently_failed",
    "cancelled",
]


class RunSummary(BaseModel):
    id: uuid.UUID
    workflow_type: str
    workflow_label: str
    ui_state: UiStateName
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class RunList(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int


class RunStepOut(BaseModel):
    ordinal: int
    step_name: str
    ui_state: UiStateName
    duration_ms: int | None
    error_summary: str | None


class LlmCallOut(BaseModel):
    purpose: str
    provider: str
    model: str
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    status: str


class RunDetail(BaseModel):
    run: RunSummary
    error_summary: str | None
    steps: list[RunStepOut]
    llm_calls: list[LlmCallOut]
