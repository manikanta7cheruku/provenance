"""ORM models. The schema itself is owned by the Alembic migrations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="USER")
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    user_agent_hash: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(CITEXT, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    target_type: Mapped[str | None] = mapped_column(Text, default=None)
    target_id: Mapped[str | None] = mapped_column(Text, default=None)
    ip_hash: Mapped[str | None] = mapped_column(Text, default=None)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileEntry(Base):
    """First tenant-owned resource. Protected by Row Level Security."""

    __tablename__ = "profile_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    entry_type: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    # "resume" for entries a parse created, "user" for entries the person added (migration 0004).
    source: Mapped[str] = mapped_column(Text, default="user")
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), default=None
    )
    # The identity key the parser gave this entry. Editing the entry does not change it, so a
    # re-parse still recognises the entry and does not add it a second time.
    source_key: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 1.6: resumes and preferences (migration 0004)


class Resume(Base):
    """One stored resume per user. Metadata only: the file lives in private storage."""

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(Text)
    file_kind: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    parse_status: Mapped[str] = mapped_column(Text, default="uploaded")
    review_status: Mapped[str] = mapped_column(Text, default="pending")
    parse_generation: Mapped[int] = mapped_column(Integer, default=1)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    char_count: Mapped[int | None] = mapped_column(Integer, default=None)
    kept_entry_count: Mapped[int] = mapped_column(Integer, default=0)
    dropped_entry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    parser_version: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ProfilePreferences(Base):
    """What the person is looking for. Typed columns so the eligibility engine can read them."""

    __tablename__ = "profile_preferences"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    authorized_countries: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    needs_sponsorship: Mapped[bool | None] = mapped_column(Boolean, default=None)
    locations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    open_to_relocate: Mapped[bool | None] = mapped_column(Boolean, default=None)
    remote_preference: Mapped[str | None] = mapped_column(Text, default=None)
    employment_types: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    min_salary_amount: Mapped[int | None] = mapped_column(Integer, default=None)
    min_salary_currency: Mapped[str | None] = mapped_column(Text, default=None)
    exclusions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 1.7: evidence chunks (migration 0005)


class EvidenceChunk(Base):
    """Searchable text for one source record. Tenant data, protected by Row Level Security.

    The embedding (vector) and the generated tsvector are deliberately not mapped: they are read
    and written with SQL in pv_persistence.evidence, so the ORM never loads a 768-number vector.
    """

    __tablename__ = "evidence_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(Text)
    source_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entry_type: Mapped[str | None] = mapped_column(Text, default=None)
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(Text, default=None)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 1.8: job postings (migration 0006)


class JobPosting(Base):
    """A posting the person pasted. Tenant data, protected by Row Level Security."""

    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    visibility: Mapped[str] = mapped_column(Text, default="private")
    source_name: Mapped[str] = mapped_column(Text)
    acquisition_method: Mapped[str] = mapped_column(Text, default="user_paste")
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    company: Mapped[str | None] = mapped_column(Text, default=None)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    parse_status: Mapped[str] = mapped_column(Text, default="queued")
    analysis_generation: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    facts_dropped: Mapped[int] = mapped_column(Integer, default=0)
    requirements_dropped: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class JobRequirement(Base):
    """One thing a posting asks for, with the posting's own words. Protected by RLS."""

    __tablename__ = "job_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    years_min: Mapped[int | None] = mapped_column(Integer, default=None)
    quote: Mapped[str] = mapped_column(Text)
    quote_start: Mapped[int] = mapped_column(Integer)
    quote_end: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 1.4: durable work and observability (migration 0003)


class WorkflowRun(Base):
    """One workflow execution. Tenant-owned: protected by Row Level Security."""

    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    workflow_type: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, default="queued")
    can_retry: Mapped[bool] = mapped_column(Boolean, default=False)
    subject_type: Mapped[str | None] = mapped_column(Text, default=None)
    subject_id: Mapped[str | None] = mapped_column(Text, default=None)
    error_class: Mapped[str | None] = mapped_column(Text, default=None)
    error_summary: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowStep(Base):
    """One step of a run. Counts and timings only, never content. Protected by RLS."""

    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    step_name: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(Text, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    error_class: Mapped[str | None] = mapped_column(Text, default=None)
    error_summary: Mapped[str | None] = mapped_column(Text, default=None)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    """A unit of background work. System table (no RLS): the worker claims across tenants.

    payload has two optional keys: args (non-sensitive references) and secret (PII or
    one-time tokens). secret is erased when the task dead-letters, everything when it
    succeeds. No API returns a payload.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(Text, default="queued")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    locked_by: Mapped[str | None] = mapped_column(Text, default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    hostname: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tasks_processed: Mapped[int] = mapped_column(Integer, default=0)


class LlmCall(Base):
    """One model call. Metadata only: no column exists for prompt or response text."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    purpose: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="ok")
    error_class: Mapped[str | None] = mapped_column(Text, default=None)
    content_hash: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserStats(Base):
    """Counters an administrator may see instead of reading tenant data. Kept by triggers."""

    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    profile_entries_count: Mapped[int] = mapped_column(Integer, default=0)
    runs_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 1.9: evidence check of a job (migration 0007)


class JobAnalysis(Base):
    """Where the evidence check of one posting stands. The band is computed on read, not stored."""

    __tablename__ = "job_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text, default="queued")
    resume_seq: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class RequirementVerdict(Base):
    __tablename__ = "requirement_verdicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="CASCADE")
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="CASCADE")
    )
    verdict: Mapped[str] = mapped_column(Text)
    evidence_kind: Mapped[str | None] = mapped_column(Text, default=None)
    reason_code: Mapped[str | None] = mapped_column(Text, default=None)
    reason: Mapped[str] = mapped_column(Text, default="")
    # [{"chunk_id": ..., "quote": ..., "content_hash": ..., "source_type": ..., "entry_type": ...}]
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    capped: Mapped[bool] = mapped_column(Boolean, default=False)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentQuestion(Base):
    __tablename__ = "agent_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="CASCADE")
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="CASCADE")
    )
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    answer: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class VerdictFeedback(Base):
    """A person's "was this right?" answer, kept with the versions that produced what they saw."""

    __tablename__ = "verdict_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="SET NULL"), default=None
    )
    subject: Mapped[str] = mapped_column(Text)
    shown: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    scoring_version: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
