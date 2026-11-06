"""ORM models. The schema itself is owned by the Alembic migrations."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
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
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
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
    # The plan the person was on when the call was made (NULL: the default plan). Lets cost be added
    # up by plan without reading any tenant table.
    plan_id: Mapped[str | None] = mapped_column(Text, default=None)
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


# ---- checkpoint 2.1: the resume studio (migration 0008)


class ResumeDocument(Base):
    """A resume built in the studio. `content` is structured JSON, never HTML. Protected by RLS."""

    __tablename__ = "resume_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, default="My resume")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumeDocumentVersion(Base):
    __tablename__ = "resume_document_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_documents.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumeExport(Base):
    __tablename__ = "resume_exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_documents.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="queued")
    storage_key: Mapped[str | None] = mapped_column(Text, default=None)
    size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# ---- checkpoint 2.4: resume tailoring (migration 0009)


class ResumeTailoring(Base):
    """One run of tailoring a resume to a job. Holds no resume text."""

    __tablename__ = "resume_tailorings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_documents.id", ondelete="CASCADE")
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text, default="queued")
    seq: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TailoringSuggestion(Base):
    __tablename__ = "tailoring_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tailoring_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_tailorings.id", ondelete="CASCADE")
    )
    unit_id: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text, default="")
    before_lines: Mapped[list[str]] = mapped_column(JSONB)
    after_lines: Mapped[list[str]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text, default="")
    # ["<requirement id>", ...]
    requirement_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # [{"chunk_id": ..., "quote": ..., "source": "profile" | "answer", "entry_type": ...}]
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # [{"text": ..., "kind": ..., "supported": bool, "source": "resume" | "evidence" | null}]
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# ---- checkpoint 2.5: source registry and company registry (migration 0010)


class JobSource(Base):
    """Where jobs can come from. Shared reference data: no Row Level Security."""

    __tablename__ = "job_sources"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    adapter: Mapped[str | None] = mapped_column(Text, default=None)
    endpoint_or_feed: Mapped[str | None] = mapped_column(Text, default=None)
    capabilities: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict)
    auth_requirements: Mapped[str] = mapped_column(Text, default="None")
    compliance_status: Mapped[str] = mapped_column(Text, default="unverified")
    terms_checked_at: Mapped[date | None] = mapped_column(Date, default=None)
    terms_url: Mapped[str | None] = mapped_column(Text, default=None)
    verification_owner: Mapped[str | None] = mapped_column(Text, default=None)
    rate_limit: Mapped[str] = mapped_column(Text, default="")
    quota_policy: Mapped[str] = mapped_column(Text, default="")
    min_poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    attribution_text: Mapped[str] = mapped_column(Text, default="")
    geographic_coverage: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supports_user_import: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_notes: Mapped[str] = mapped_column(Text, default="")
    health_status: Mapped[str] = mapped_column(Text, default="unknown")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    failure_streak: Mapped[int] = mapped_column(Integer, default=0)
    breaker_open_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyRow(Base):
    __tablename__ = "companies"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    domain: Mapped[str | None] = mapped_column(Text, default=None)
    career_url: Mapped[str | None] = mapped_column(Text, default=None)
    ats_platform: Mapped[str | None] = mapped_column(Text, default=None)
    ats_board_id: Mapped[str | None] = mapped_column(Text, default=None)
    industry: Mapped[str | None] = mapped_column(Text, default=None)
    country: Mapped[str | None] = mapped_column(Text, default=None)
    last_verified_at: Mapped[date | None] = mapped_column(Date, default=None)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 2.6: jobs fetched from sources (migration 0011)


class SourceJob(Base):
    """One job as a source published it. Shared reference data: no Row Level Security."""

    __tablename__ = "source_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(ForeignKey("job_sources.key", ondelete="CASCADE"))
    board_id: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    company_name: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str] = mapped_column(Text, default="")
    workplace: Mapped[str | None] = mapped_column(Text, default=None)
    employment_type: Mapped[str | None] = mapped_column(Text, default=None)
    department: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    content_hash: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    company_norm: Mapped[str | None] = mapped_column(Text, default=None)
    title_norm: Mapped[str | None] = mapped_column(Text, default=None)
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    seen_count: Mapped[int] = mapped_column(Integer, default=1)


class SourceTarget(Base):
    __tablename__ = "source_targets"

    source_key: Mapped[str] = mapped_column(
        ForeignKey("job_sources.key", ondelete="CASCADE"), primary_key=True
    )
    board_id: Mapped[str] = mapped_column(Text, primary_key=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_outcome: Mapped[str | None] = mapped_column(Text, default=None)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    jobs_open: Mapped[int] = mapped_column(Integer, default=0)


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(ForeignKey("job_sources.key", ondelete="CASCADE"))
    board_id: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer, default=None)
    bytes_read: Mapped[int] = mapped_column(Integer, default=0)
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_changed: Mapped[int] = mapped_column(Integer, default=0)
    jobs_closed: Mapped[int] = mapped_column(Integer, default=0)
    jobs_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[str | None] = mapped_column(Text, default=None)


# ---- checkpoint 2.7: duplicate detection (migration 0012)


class SourceJobLink(Base):
    """An edge between two fetched jobs believed to be the same job. Shared reference data."""

    __tablename__ = "source_job_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_a: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_jobs.id", ondelete="CASCADE"))
    job_b: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_jobs.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(Text)
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    reason: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class PostingLink(Base):
    """A person decision about a public job and a posting they pasted. Protected by RLS."""

    __tablename__ = "posting_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    source_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_jobs.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 2.8: imports (migration 0013)


class ImportBatch(Base):
    """One spreadsheet upload or one web address a person asked us to read. Protected by RLS."""

    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    default_source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued")
    file_key: Mapped[str | None] = mapped_column(Text, default=None)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    ignored_columns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ImportItem(Base):
    """One row of an import report. Never holds posting text. Protected by RLS."""

    __tablename__ = "import_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    row_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="queued")
    code: Mapped[str | None] = mapped_column(Text, default=None)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    posting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 2.9: the workbench (migration 0014)


class JobDecision(Base):
    """What a person has decided about one posting. No row means new. Protected by RLS."""

    __tablename__ = "job_decisions"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), primary_key=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(Text, default="new")
    note: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobDecisionEvent(Base):
    """One move of a decision. Holds no note text. Protected by RLS."""

    __tablename__ = "job_decision_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(Text)
    from_state: Mapped[str] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkbenchView(Base):
    """A saved view: a name and a validated query. Protected by RLS."""

    __tablename__ = "workbench_views"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    query: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 2.10: the shortlist email and application drafts (migration 0015)


class ApplicationDraft(Base):
    """A cover note or an answer for one posting, for the person to edit. Protected by RLS."""

    __tablename__ = "application_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, default="")
    question_key: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="queued")
    origin: Mapped[str] = mapped_column(Text, default="model")
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    seq: Mapped[int] = mapped_column(Integer, default=1)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShortlistSettings(Base):
    """A person's shortlist email schedule. Off until they turn it on. Protected by RLS."""

    __tablename__ = "shortlist_settings"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(Text, default="weekly")
    weekday: Mapped[int] = mapped_column(Integer, default=0)
    hour: Mapped[int] = mapped_column(Integer, default=8)
    timezone: Mapped[str] = mapped_column(Text, default="UTC")
    max_items: Mapped[int] = mapped_column(Integer, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShortlistRun(Base):
    """One due time of the shortlist and what came of it. Protected by RLS."""

    __tablename__ = "shortlist_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    slot: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShortlistItem(Base):
    """A job that was in a shortlist email, so it is never sent twice. Protected by RLS."""

    __tablename__ = "shortlist_items"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shortlist_runs.id", ondelete="CASCADE"), primary_key=True
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), primary_key=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)


# ---- checkpoint 2.11: pictures for the resume studio (migration 0016)


class ResumeImage(Base):
    """A stored picture. The bytes are in private storage. Protected by RLS."""

    __tablename__ = "resume_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumeTheme(Base):
    """A saved font pair and four colors. Protected by RLS."""

    __tablename__ = "resume_themes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    font_pair: Mapped[str] = mapped_column(Text)
    accent: Mapped[str] = mapped_column(Text)
    ink: Mapped[str] = mapped_column(Text)
    muted: Mapped[str] = mapped_column(Text)
    tint: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 3.1: the GitHub connection (migration 0018)


class GitHubConnection(Base):
    """A person's GitHub connection. The token is sealed (encrypted). Protected by RLS."""

    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    github_user_id: Mapped[int] = mapped_column(BigInteger)
    login: Mapped[str] = mapped_column(Text)
    token_sealed: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text, default="")
    sync_state: Mapped[str] = mapped_column(Text, default="idle")
    sync_error: Mapped[str | None] = mapped_column(Text, default=None)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class GitHubOAuthState(Base):
    """A started sign-in: a hash of the state and the sealed PKCE verifier. Protected by RLS."""

    __tablename__ = "github_oauth_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    state_hash: Mapped[str] = mapped_column(Text)
    verifier_sealed: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class GitHubRepo(Base):
    """A public repository as last read, so the person can choose which become evidence. RLS."""

    __tablename__ = "github_repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    html_url: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    fork: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_remote: Mapped[str] = mapped_column(Text, default="")
    pushed_remote: Mapped[str] = mapped_column(Text, default="")
    suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    readme_excerpt: Mapped[str] = mapped_column(Text, default="")
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 3.2: career preparation (migration 0019)


class JobPreparation(Base):
    """The interview date and the person's own notes about a company, for one job. RLS."""

    __tablename__ = "job_preparations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    interview_date: Mapped[date | None] = mapped_column(Date, default=None)
    company_link: Mapped[str] = mapped_column(Text, default="")
    company_notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrepOutput(Base):
    """One kind of preparation for one job: questions, topics, or a message to send. RLS."""

    __tablename__ = "prep_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued")
    origin: Mapped[str] = mapped_column(Text, default="model")
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    seq: Mapped[int] = mapped_column(Integer, default=1)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    prompt_version: Mapped[str | None] = mapped_column(Text, default=None)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    body: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrepProgress(Base):
    """What the person has ticked as done, by a stable key. RLS."""

    __tablename__ = "prep_progress"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    item_key: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MockInterview(Base):
    """A practice session: the questions, and each answer with its feedback. RLS."""

    __tablename__ = "mock_interviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(Text, default="active")
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# ---- checkpoint 3.3: plans, entitlements and the usage ledger (migration 0020)


class Plan(Base):
    """A plan and its limits, as data. Readable by everyone, changed only by the database owner."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPlan(Base):
    """Which plan a person is on. No row means the default plan. Protected by RLS."""

    __tablename__ = "user_plans"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"))
    assigned_by: Mapped[str] = mapped_column(Text, default="operator")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UsageLedger(Base):
    """One billable event. The same key in the same month is the same event. Protected by RLS."""

    __tablename__ = "usage_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    unit: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer, default=1)
    period_start: Mapped[date] = mapped_column(Date)
    event_key: Mapped[str] = mapped_column(Text)
    plan_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- checkpoint 3.4: report exports (migration 0021)


class ReportExport(Base):
    """A report a person asked for. The file is in private storage. Protected by RLS."""

    __tablename__ = "report_exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text, default="opportunities")
    format: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(Text, default="queued")
    storage_key: Mapped[str | None] = mapped_column(Text, default=None)
    size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---- checkpoint 3.6: evaluation runs (migration 0022)


class EvaluationRun(Base):
    """One evaluation run. System table: synthetic data, no owner, append-only for the app."""

    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    suite: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text, default="manual")
    dataset_version: Mapped[str] = mapped_column(Text)
    git_sha: Mapped[str | None] = mapped_column(Text, default=None)
    model: Mapped[str | None] = mapped_column(Text, default=None)
    passed: Mapped[bool] = mapped_column(Boolean)
    case_count: Mapped[int] = mapped_column(Integer)
    failure_count: Mapped[int] = mapped_column(Integer)
    versions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    suites: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    failures: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)


# ---- checkpoint 3.7: account deletion (migration 0023)


class AccountDeletion(Base):
    """That a deletion happened. No user id, no email, nothing traceable to a person."""

    __tablename__ = "account_deletions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[str] = mapped_column(Text, default="queued")
    files_removed: Mapped[int] = mapped_column(Integer, default=0)
    stray_rows_removed: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
