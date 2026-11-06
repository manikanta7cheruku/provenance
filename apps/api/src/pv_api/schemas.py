"""Request and response models. FastAPI turns these into the OpenAPI documentation."""

import json
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    # "resume" when a parse created it, "user" when the person added it. Editing keeps the source
    # and sets user_edited, so the screen can say "from your resume" or "added or edited by you".
    source: str = "user"
    # Recommended fields still empty (advice shown as "needs correction", never a block).
    flags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FieldSpecOut(BaseModel):
    name: str
    label: str
    kind: str
    max_length: int
    required: bool
    recommended: bool
    hint: str


class EntrySpecOut(BaseModel):
    entry_type: str
    label: str
    plural: str
    primary_field: str
    fields: list[FieldSpecOut]


# ---- resume (checkpoint 1.6)
class ResumeOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_kind: Literal["pdf", "docx"]
    size_bytes: int
    # What the person is shown. The browser adds Idle and Uploading itself.
    ui_state: Literal["uploaded", "parsing", "parsed", "needs_correction", "confirmed", "failed"]
    can_retry: bool
    # A plain sentence when ui_state is "failed".
    error_message: str | None
    kept_entry_count: int
    # Entries the model proposed that were not found in the resume text, so they were not stored.
    dropped_entry_count: int
    flagged_entry_count: int
    page_count: int | None
    run_id: uuid.UUID | None
    created_at: datetime
    parsed_at: datetime | None
    confirmed_at: datetime | None


# ---- preferences (checkpoint 1.6)
RemotePreference = Literal["remote", "hybrid", "onsite", "any"]
EmploymentType = Literal["full_time", "part_time", "internship", "contract", "freelance"]
Currency = Literal["INR", "USD", "CAD", "GBP", "EUR", "AED", "SGD", "AUD"]


def _clean_list(values: list[str], *, max_items: int, max_length: int) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = " ".join(value.split())
        if not text:
            continue
        if len(text) > max_length:
            raise ValueError(f"Each item must be at most {max_length} characters.")
        if text.casefold() not in {c.casefold() for c in cleaned}:
            cleaned.append(text)
    if len(cleaned) > max_items:
        raise ValueError(f"Enter at most {max_items} items.")
    return cleaned


class PreferencesIn(BaseModel):
    target_roles: list[str] = Field(default_factory=list, max_length=60)
    authorized_countries: list[str] = Field(default_factory=list, max_length=60)
    needs_sponsorship: bool | None = None
    locations: list[str] = Field(default_factory=list, max_length=60)
    open_to_relocate: bool | None = None
    remote_preference: RemotePreference | None = None
    employment_types: list[EmploymentType] = Field(default_factory=list, max_length=5)
    min_salary_amount: int | None = Field(default=None, ge=0, le=1_000_000_000)
    min_salary_currency: Currency | None = None
    exclusions: list[str] = Field(default_factory=list, max_length=60)

    @field_validator("target_roles", "exclusions")
    @classmethod
    def _short_lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value, max_items=20, max_length=80)

    @field_validator("authorized_countries", "locations")
    @classmethod
    def _place_lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value, max_items=30, max_length=60)

    @field_validator("employment_types")
    @classmethod
    def _unique_types(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _salary_pair(self) -> "PreferencesIn":
        if (self.min_salary_amount is None) != (self.min_salary_currency is None):
            raise ValueError("Enter both an amount and a currency, or neither.")
        return self


class PreferencesOut(PreferencesIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime | None = None


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
    step_label: str = ""
    ui_state: UiStateName
    duration_ms: int | None
    error_summary: str | None
    # Counts the step recorded (jobs read, bytes written). Numbers only, never text.
    counts: dict[str, int] = Field(default_factory=dict)


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


class RunFailureOut(BaseModel):
    what: str
    next: str
    retry_possible: bool


class RunTotalsOut(BaseModel):
    steps: int
    steps_failed: int
    model_calls: int
    model_calls_failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    models: list[str]
    prompt_versions: list[str]


class RunDetail(BaseModel):
    run: RunSummary
    error_summary: str | None
    steps: list[RunStepOut]
    llm_calls: list[LlmCallOut]
    subject_label: str | None = None
    subject_path: str | None = None
    failure: RunFailureOut | None = None
    totals: RunTotalsOut | None = None


# ---- evidence search (checkpoint 1.7)
class EvidenceStatusOut(BaseModel):
    indexed: int
    embedded: int
    pending: int
    # True when an AI key and an embedding model are set. Keyword search never needs them.
    meaning_search_configured: bool


class EvidenceSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter something to search for.")
        return value


class EvidenceHitOut(BaseModel):
    chunk_id: uuid.UUID
    # The profile entry this text came from, so the screen can link to it. None for other sources.
    entry_id: uuid.UUID | None
    source_type: str
    entry_type: str | None
    text: str
    score: float
    # Which searches found it: keyword, meaning or both.
    matched_by: list[str]
    keyword_rank: int | None
    meaning_rank: int | None
    similarity: float | None


class EvidenceSearchOut(BaseModel):
    query: str
    meaning_search_used: bool
    # A plain sentence when meaning search was not used, such as "needs an AI key".
    note: str | None
    hits: list[EvidenceHitOut]


# ---- job postings (checkpoint 1.8)
class JobCreate(BaseModel):
    source_name: str = Field(min_length=1, max_length=80)
    source_url: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=1, max_length=40_000)

    @field_validator("source_name")
    @classmethod
    def _clean_source(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Say where this posting came from.")
        return cleaned

    @field_validator("source_url")
    @classmethod
    def _clean_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not cleaned.lower().startswith(("https://", "http://")) or " " in cleaned:
            raise ValueError("Enter a full address that starts with https:// or http://.")
        return cleaned


class FactOut(BaseModel):
    value: str | int | list[str]
    # The posting's own words behind the fact.
    quote: str


class GateOut(BaseModel):
    gate: str
    label: str
    state: Literal["eligible", "not_eligible", "uncertain", "requires_user_input"]
    reason: str
    posting_quote: str | None


class EligibilityOut(BaseModel):
    state: Literal["eligible", "not_eligible", "uncertain", "requires_user_input"]
    rules_version: str
    # Worst first, so a blocker is never buried.
    gates: list[GateOut]


class RequirementOut(BaseModel):
    id: uuid.UUID
    ordinal: int
    text: str
    kind: Literal["required", "preferred"]
    category: str
    years_min: int | None
    quote: str
    quote_start: int
    quote_end: int


class JobSummaryOut(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    source_name: str
    # How the text reached us, said honestly: "user_paste" means the person pasted it.
    acquisition_method: str
    ui_state: Literal["reading", "ready", "failed"]
    can_retry: bool
    error_message: str | None
    eligibility: Literal["eligible", "not_eligible", "uncertain", "requires_user_input"] | None
    work_mode: str | None
    location: str | None
    requirement_count: int
    created_at: datetime


class JobDetailOut(JobSummaryOut):
    source_url: str | None
    visibility: str
    facts: dict[str, FactOut]
    requirements: list[RequirementOut]
    eligibility_detail: EligibilityOut | None
    decision: "DecisionOut | None" = None
    # How many things the reader suggested that were not in the posting, so were left out.
    facts_dropped: int
    requirements_dropped: int
    prompt_version: str | None
    run_id: uuid.UUID | None
    extracted_at: datetime | None
    # The person's own pasted text, so the screen can show each quote in place.
    text: str


class JobCreatedOut(BaseModel):
    job: JobDetailOut
    # True when this exact posting was pasted before. Nothing was read again.
    duplicate: bool


# ---- checkpoint 1.9: the evidence check of a job


class CitationOut(BaseModel):
    chunk_id: uuid.UUID
    quote: str
    # Where the words came from: the profile or an answer the person gave for this job.
    source: Literal["profile", "answer"]
    entry_type: str | None
    # True when the entry was edited or removed after the check, so the quote may be out of date.
    changed: bool


class VerdictOut(BaseModel):
    requirement_id: uuid.UUID
    requirement: str
    kind: Literal["required", "preferred"]
    category: str
    posting_quote: str
    # None while the agent has not reached this requirement or is waiting for the person.
    verdict: Literal["met", "partial", "not_verified", "conflicting"] | None
    evidence_kind: Literal["direct", "inferred"] | None
    confidence: Literal["high", "medium", "none"] | None
    citations: list[CitationOut]
    # The reader's own note when there is evidence. A fixed sentence when there is none.
    reason: str
    capped: bool
    feedback: Literal["right", "wrong"] | None


class GateRequirementOut(BaseModel):
    requirement_id: uuid.UUID
    requirement: str
    kind: Literal["required", "preferred"]


class QuestionOut(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    requirement: str
    question: str
    status: Literal["pending", "answered", "skipped"]
    answer: str | None


class GapOut(BaseModel):
    requirement_id: uuid.UUID
    requirement: str
    state: str
    proof_needed: str
    next_step: str


class ScoreOut(BaseModel):
    scoring_version: str
    band: Literal["strong", "good", "review", "not_recommended", "not_eligible"]
    required_total: int
    met: int
    partial: int
    conflicting: int
    not_verified: int
    preferred_total: int
    preferred_supported: int
    reasons: list[str]


class AnalysisOut(BaseModel):
    ui_state: Literal["not_started", "working", "needs_answer", "ready", "failed"]
    can_start: bool
    # Why the check cannot be started now, in a sentence, or None.
    blocker: str | None
    error_message: str | None
    checked: int
    total: int
    # Only present when every requirement has a verdict. Never a partial score.
    score: ScoreOut | None
    verdicts: list[VerdictOut]
    gate_requirements: list[GateRequirementOut]
    questions: list[QuestionOut]
    gaps: list[GapOut]
    # True when any cited entry changed after the check.
    stale: bool
    recommendation_feedback: Literal["right", "wrong"] | None
    scoring_version: str
    prompt_version: str | None


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


class FeedbackIn(BaseModel):
    # None means the recommendation as a whole.
    requirement_id: uuid.UUID | None = None
    answer: Literal["right", "wrong"]
    note: str | None = Field(default=None, max_length=1000)


# ---- checkpoint 2.1: the resume studio


class ResumeCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    start: Literal["profile", "blank"] = "profile"
    template: Literal["classic", "modern", "compact"] = "classic"

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str | None) -> str | None:
        cleaned = " ".join(value.split()) if value else None
        return cleaned or None


class ResumeSave(BaseModel):
    content: dict[str, Any]
    # The revision this edit started from. A save from an older revision is refused.
    revision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=120)
    # True for a deliberate "save a restore point" rather than an automatic save.
    checkpoint: bool = False


class ResumePreview(BaseModel):
    content: dict[str, Any]


class ResumeDocumentSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    revision: int
    template: str
    updated_at: datetime


class ResumeDocumentOut(ResumeDocumentSummaryOut):
    content: dict[str, Any]


class PreviewOut(BaseModel):
    html: str


class VersionOut(BaseModel):
    id: uuid.UUID
    revision: int
    created_at: datetime


class RestoreIn(BaseModel):
    # The revision the person is looking at, so a restore cannot overwrite a newer save.
    revision: int = Field(ge=1)


class ExportOut(BaseModel):
    id: uuid.UUID
    revision: int
    ui_state: Literal["preparing", "ready", "failed"]
    size_bytes: int | None
    page_count: int | None
    error_message: str | None
    created_at: datetime


class TemplateOut(BaseModel):
    key: str
    name: str
    description: str
    ats_safe: bool


class StudioOptionsOut(BaseModel):
    templates: list[TemplateOut]
    font_pairs: list[dict[str, str]]
    sizes: list[str]
    spacings: list[str]
    margins: list[str]
    dividers: list[str]
    papers: list[str]
    section_kinds: list[str]
    max_resumes: int


# ---- checkpoint 2.4: resume tailoring


class TailorStartIn(BaseModel):
    job_id: uuid.UUID


class TailorJobOut(BaseModel):
    job_id: uuid.UUID
    title: str | None
    company: str | None


class TailorRequirementOut(BaseModel):
    id: uuid.UUID
    text: str


class TailorCitationOut(BaseModel):
    chunk_id: uuid.UUID
    quote: str
    source: str
    entry_type: str | None


class TailorClaimOut(BaseModel):
    text: str
    kind: str
    supported: bool
    source: str | None


class TailorSuggestionOut(BaseModel):
    id: uuid.UUID
    unit_id: str
    kind: str
    label: str
    before_lines: list[str]
    after_lines: list[str]
    reason: str
    requirements: list[TailorRequirementOut]
    citations: list[TailorCitationOut]
    claims: list[TailorClaimOut]
    blocked: bool
    edited: bool
    status: str


class TailorGapOut(BaseModel):
    text: str
    reason: str


class TailoringOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str | None
    company: str | None
    ui_state: str
    error_message: str | None
    suggestions: list[TailorSuggestionOut]
    unclaimed: list[TailorGapOut]


class SuggestionEditIn(BaseModel):
    after_lines: list[str]


class SuggestionAcceptIn(BaseModel):
    revision: int


class SuggestionAcceptedOut(BaseModel):
    suggestion: TailorSuggestionOut
    document: ResumeDocumentSummaryOut


# ---- checkpoint 2.5: sources, companies and the search plan


class SearchPlanIn(BaseModel):
    """A typed sentence, or an intent the person filled in. The sentence needs the AI service."""

    query: str | None = None
    intent: dict[str, Any] | None = None


class SourceOut(BaseModel):
    key: str
    display_name: str
    source_type: str
    outcome: str
    message: str
    reason: str | None
    import_available: bool
    compliance_status: str
    terms_checked_at: date | None
    terms_url: str | None
    attribution_text: str
    capabilities: dict[str, bool]
    health_status: str = "unknown"
    last_success_at: datetime | None = None
    jobs_open: int = 0


class SourceDecisionOut(BaseModel):
    key: str
    display_name: str
    outcome: str
    message: str
    reason: str | None
    import_available: bool
    named_by_person: bool
    notes: list[str]


class CompanyCandidateOut(BaseModel):
    key: str
    name: str
    score: float


class CompanyDecisionOut(BaseModel):
    query: str
    status: str
    route: str
    message: str
    company: CompanyCandidateOut | None
    source_key: str | None
    candidates: list[CompanyCandidateOut]


class AuthorizationOut(BaseModel):
    countries: list[str]
    needs_sponsorship: bool | None
    origin: str


class SearchPlanOut(BaseModel):
    interpreted_by: str
    intent: dict[str, Any]
    headline: str
    can_search_now: bool
    notes: list[str]
    sources: list[SourceDecisionOut]
    companies: list[CompanyDecisionOut]
    authorization: AuthorizationOut


class AdminSourceOut(BaseModel):
    key: str
    display_name: str
    source_type: str
    adapter: str | None
    endpoint_or_feed: str | None
    capabilities: dict[str, bool]
    auth_requirements: str
    compliance_status: str
    terms_checked_at: date | None
    terms_url: str | None
    verification_owner: str | None
    rate_limit: str
    quota_policy: str
    min_poll_interval_seconds: int
    attribution_text: str
    geographic_coverage: list[str]
    enabled: bool
    compliance_notes: str
    health_status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    failure_streak: int
    review_expired: bool
    enable_blocker: str | None
    edited: bool
    breaker_open_until: datetime | None = None
    jobs_open: int = 0


class SourceUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    compliance_status: str | None = None
    terms_checked_at: date | None = None
    terms_url: str | None = None
    verification_owner: str | None = None
    rate_limit: str | None = None
    quota_policy: str | None = None
    min_poll_interval_seconds: int | None = None
    attribution_text: str | None = None
    geographic_coverage: list[str] | None = None
    compliance_notes: str | None = None


# ---- checkpoint 2.6: fetched jobs and source health


class SightingOut(BaseModel):
    """One place a job was seen: the copy a person pasted, or a posting fetched from a source."""

    kind: str
    source_name: str
    board_id: str | None
    title: str
    location: str
    url: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int
    closed: bool
    how: str


class SourceJobOut(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str | None
    location: str
    workplace: str | None
    employment_type: str | None
    department: str
    url: str
    excerpt: str
    source_key: str
    source_name: str
    attribution_text: str
    posted_at: datetime | None
    first_seen_at: datetime
    also_seen: list[SightingOut] = []


class FetchLogOut(BaseModel):
    started_at: datetime
    board_id: str | None
    outcome: str
    http_status: int | None
    duration_ms: int
    jobs_seen: int
    jobs_new: int
    jobs_changed: int
    jobs_closed: int
    jobs_skipped: int
    error_class: str | None


class PollQueuedOut(BaseModel):
    message: str


# ---- checkpoint 2.7: duplicates, links and sightings


class PostingMatchOut(BaseModel):
    group_id: uuid.UUID
    title: str
    company_name: str | None
    location: str
    source_name: str
    url: str
    method: str
    score: float
    reason: str
    state: str
    sightings: list[SightingOut]


class JobMatchesOut(BaseModel):
    note: str | None
    sightings: list[SightingOut]
    matches: list[PostingMatchOut]


class LinkedJobOut(BaseModel):
    title: str
    company_name: str | None
    location: str
    source_key: str
    url: str


class AdminLinkOut(BaseModel):
    id: uuid.UUID
    state: str
    method: str
    score: float
    reason: str
    created_at: datetime
    decided_at: datetime | None
    first: LinkedJobOut
    second: LinkedJobOut


# ---- checkpoint 2.8: imports
class JobManualIn(BaseModel):
    """A job typed in by hand. The fields become the posting text, which is read like any paste."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=400)
    company: str = Field(default="", max_length=400)
    location: str = Field(default="", max_length=400)
    source_name: str = Field(default="Other", min_length=1, max_length=80)
    source_url: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=1, max_length=40_000)

    @field_validator("title")
    @classmethod
    def _title_present(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Enter the job title.")
        return cleaned


class ImportUrlIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2000)
    source_name: str = Field(default="Company career page", min_length=1, max_length=80)


class ImportItemOut(BaseModel):
    row_number: int
    status: Literal["queued", "created", "duplicate", "rejected"]
    code: str | None
    message: str | None
    title: str | None
    source_url: str | None
    posting_id: uuid.UUID | None


class ImportBatchOut(BaseModel):
    id: uuid.UUID
    kind: Literal["csv", "xlsx", "url"]
    label: str
    default_source: str
    status: Literal["queued", "running", "done", "failed"]
    error_message: str | None
    total_rows: int
    created_count: int
    duplicate_count: int
    rejected_count: int
    ignored_columns: list[str]
    created_at: datetime
    finished_at: datetime | None


class ImportDetailOut(ImportBatchOut):
    items: list[ImportItemOut]


# ---- checkpoint 2.9: the workbench
DecisionActionName = Literal[
    "save",
    "unsave",
    "dismiss",
    "undo_dismiss",
    "approve",
    "mark_applied",
    "undo_applied",
    "archive",
]


class ActionOut(BaseModel):
    action: DecisionActionName
    label: str


class DecisionOut(BaseModel):
    state: Literal["new", "saved", "dismissed", "approved_for_prep", "applied", "archived"]
    state_label: str
    # What the interface offers now, in order. The server decides, the browser only shows.
    actions: list[ActionOut]
    note: str
    applied_at: datetime | None
    updated_at: datetime | None


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DecisionActionName
    # For mark_applied: the day the person applied. Not in the future. Today when left out.
    applied_on: date | None = None


class DecisionResultOut(BaseModel):
    decision: DecisionOut
    # The action that takes this one back, when it can be. The interface offers it as Undo.
    undo: DecisionActionName | None
    undo_label: str | None


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(max_length=2000)


class WorkRowOut(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    source_name: str
    acquisition_method: str
    work_mode: str | None
    location: str | None
    employment_type: str | None
    seniority: str | None
    eligibility: str | None
    band: str | None
    reading: Literal["reading", "ready", "failed"]
    decision: DecisionOut
    has_note: bool
    created_at: datetime


class FacetsOut(BaseModel):
    views: dict[str, int]
    work_modes: dict[str, int]
    eligibility: dict[str, int]
    bands: dict[str, int]
    employment_types: dict[str, int]
    seniorities: dict[str, int]
    sources: dict[str, int]


class WorkbenchOut(BaseModel):
    rows: list[WorkRowOut]
    # Rows that match the filters, which may be more than the rows returned.
    total: int
    # The query as it was understood: unknown values are dropped, not guessed at.
    query: dict[str, Any]
    facets: FacetsOut
    truncated: bool


class BulkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: DecisionActionName

    @field_validator("ids")
    @classmethod
    def _unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Each job may be listed once.")
        return value


class BulkItemOut(BaseModel):
    id: uuid.UUID
    ok: bool
    state: str | None
    message: str | None


class BulkOut(BaseModel):
    results: list[BulkItemOut]
    done: int
    skipped: int
    undo: DecisionActionName | None
    undo_label: str | None


class ViewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    query: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Give the view a name.")
        return cleaned

    @field_validator("query")
    @classmethod
    def _small_query(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value)) > 4000:
            raise ValueError("This view has too many filters.")
        return value


class ViewOut(BaseModel):
    id: uuid.UUID
    name: str
    query: dict[str, Any]
    created_at: datetime


JobDetailOut.model_rebuild()


# ---- checkpoint 2.10: application drafts and the shortlist email
class DraftClaimOut(BaseModel):
    text: str
    kind: str
    supported: bool
    source: str | None


class DraftEvidenceOut(BaseModel):
    text: str
    source: str
    cited: bool


class DraftOut(BaseModel):
    id: uuid.UUID
    kind: Literal["cover_note", "answer"]
    question: str
    body: str
    # queued and working are both "working" to the person
    ui_state: Literal["working", "ready", "failed"]
    origin: Literal["model", "edited"]
    error_message: str | None
    claims: list[DraftClaimOut]
    unsupported_count: int
    word_count: int
    evidence: list[DraftEvidenceOut]
    updated_at: datetime


class DraftQuestionOut(BaseModel):
    key: str
    text: str


class DraftsOut(BaseModel):
    drafts: list[DraftOut]
    can_write: bool
    blocker: str | None
    questions: list[DraftQuestionOut]
    max_drafts: int
    # Said every time a draft is shown. The product never sends a draft and never applies.
    label: str


class DraftStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cover_note", "answer"]
    question: str = Field(default="", max_length=600)
    # The draft was edited. Starting again throws the edits away, so it must be asked for.
    replace: bool = False


class DraftEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=9000)


class ShortlistSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    frequency: Literal["daily", "weekly"]
    weekday: int = Field(default=0, ge=0, le=6)
    hour: int = Field(ge=0, le=23)
    timezone: str = Field(min_length=1, max_length=64)
    max_items: int = Field(default=5, ge=1, le=10)


class ShortlistSettingsOut(BaseModel):
    enabled: bool
    frequency: Literal["daily", "weekly"]
    weekday: int
    hour: int
    timezone: str
    max_items: int
    schedule_text: str
    next_run_at: datetime | None
    last_run_at: datetime | None


class ShortlistRunOut(BaseModel):
    outcome: Literal["sent", "nothing", "skipped", "failed"]
    outcome_text: str
    item_count: int
    manual: bool
    at: datetime


class ShortlistOut(BaseModel):
    settings: ShortlistSettingsOut
    runs: list[ShortlistRunOut]
    email_verified: bool
    # Why the email cannot be turned on yet, when it cannot.
    blocker: str | None
    delivery_note: str


class ShortlistItemOut(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    location: str | None
    band: str | None
    eligibility: str | None
    reason: str


class ShortlistPreviewOut(BaseModel):
    items: list[ShortlistItemOut]
    note: str


class ShortlistSendOut(BaseModel):
    queued: bool
    message: str


# ---- checkpoint 2.11: pictures for the resume studio
class ImageOut(BaseModel):
    id: uuid.UUID
    width: int
    height: int
    mime: str
    size_bytes: int
    original_name: str
    created_at: datetime
    # Whether a resume (or a saved version of one) still uses it, so it cannot be deleted yet.
    used: bool
    url: str


class ImagesOut(BaseModel):
    images: list[ImageOut]
    count: int
    max_images: int
    max_bytes: int
    used_bytes: int
    accepted: list[str]


# ---- checkpoint 2.13: saved themes for the resume studio
class ThemeIn(BaseModel):
    """What the person sends. The rules (readable colors, a known font pair) are in the domain."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    font_pair: str = Field(max_length=100)
    accent: str = Field(max_length=20)
    ink: str = Field(max_length=20)
    muted: str = Field(max_length=20)
    tint: str = Field(max_length=20)


class ThemeOut(BaseModel):
    id: uuid.UUID
    name: str
    font_pair: str
    accent: str
    ink: str
    muted: str
    tint: str
    updated_at: datetime


class ThemesOut(BaseModel):
    themes: list[ThemeOut]
    count: int
    max_themes: int


# ---- checkpoint 3.1: the GitHub connection
class PlatformOut(BaseModel):
    name: str
    why: str
    what: str


class GitHubRepoOut(BaseModel):
    id: int
    full_name: str
    name: str
    description: str
    language: str
    topics: list[str]
    stars: int
    fork: bool
    archived: bool
    url: str
    selected: bool
    suggested: bool
    has_excerpt: bool


class GitHubOut(BaseModel):
    # Whether the operator has set up GitHub on this server at all.
    available: bool
    connected: bool
    login: str | None
    profile_url: str | None
    # The permission asked of GitHub. Empty means none: public information only.
    scope: str
    scope_sentence: str
    sync_state: str
    sync_error: str | None
    connected_at: datetime | None
    last_synced_at: datetime | None
    repos: list[GitHubRepoOut]
    max_selected: int
    entries_from_github: int
    # Places that cannot be connected, and what to do instead.
    platforms: list[PlatformOut]


class GitHubStartOut(BaseModel):
    authorize_url: str


class GitHubFinishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=300)
    state: str = Field(min_length=20, max_length=200)


class GitHubFinishOut(BaseModel):
    login: str


class GitHubChooseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_ids: list[int] = Field(max_length=200)


class GitHubDisconnectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Keep the entries GitHub made. They become the person's own.
    keep_entries: bool = False


class GitHubDisconnectOut(BaseModel):
    revoked: bool
    entries_removed: int


# ---- checkpoint 3.2: career preparation
class PrepClaimOut(BaseModel):
    text: str
    kind: str
    supported: bool
    source: str | None


class PrepItemOut(BaseModel):
    key: str
    text: str
    guidance: str
    category: str
    difficulty: str
    requirement_id: str | None
    evidence_count: int
    insufficient_evidence: bool
    note: str
    claims: list[PrepClaimOut]
    unsupported_count: int
    done: bool


class PrepEvidenceOut(BaseModel):
    text: str
    source: str
    cited: bool


class PrepActionOut(BaseModel):
    key: str
    label: str
    description: str
    shape: str
    # None when nothing has been made yet.
    status: str | None
    error: str | None
    origin: str | None
    items: list[PrepItemOut]
    body: str
    word_count: int
    claims: list[PrepClaimOut]
    evidence: list[PrepEvidenceOut]
    updated_at: datetime | None


class PrepConceptOut(BaseModel):
    key: str
    requirement_id: str
    text: str
    kind: str
    category: str
    verdict: str
    priority: str
    priority_label: str
    difficulty: str
    why: str
    done: bool


class PrepCoverageOut(BaseModel):
    required: int
    met: int
    partial: int
    not_shown: int
    unchecked: int


class PrepPlanDayOut(BaseModel):
    date: date
    kind: str
    topics: list[str]


class PrepCompanyOut(BaseModel):
    name: str
    location: str
    source_name: str
    source_url: str | None
    link: str
    notes: str
    says: list[str]


class PrepProgressOut(BaseModel):
    done: int
    total: int
    percent: int


class MockRubricOut(BaseModel):
    name: str
    score: int
    note: str


class MockTurnOut(BaseModel):
    question: str
    answer: str
    rubric: list[MockRubricOut]
    total: int
    maximum: int
    unsupported_claims: list[str]
    follow_up: str
    words: int


class MockOut(BaseModel):
    id: uuid.UUID
    state: str
    question_count: int
    turns: list[MockTurnOut]
    current_question: str | None
    current_index: int


class PreparationOut(BaseModel):
    job_id: uuid.UUID
    title: str
    company: str
    can_prepare: bool
    blocker: str | None
    family: str
    years: int
    rules_version: str
    coverage: PrepCoverageOut
    concepts: list[PrepConceptOut]
    actions: list[PrepActionOut]
    interview_date: date | None
    plan: list[PrepPlanDayOut]
    company_info: PrepCompanyOut
    progress: PrepProgressOut
    mock: MockOut | None
    likely_label: str
    generated_label: str


class PrepDateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interview_date: date | None = None


class PrepCompanyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=4000)


class PrepProgressIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    done: bool


class PrepTextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=6000)


class MockAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(max_length=6000)


# ---- checkpoint 3.3: plans and usage
class QuotaOut(BaseModel):
    unit: str
    label: str
    noun: str
    help: str
    used: int
    # None means no limit.
    limit: int | None
    remaining: int | None
    percent: int
    # "ok", "near" or "reached"
    state: str


class PlanChoiceOut(BaseModel):
    id: str
    label: str
    current: bool
    limits: dict[str, int | None]
    resumes: int
    exports_per_resume: int


class UsageEventOut(BaseModel):
    label: str
    amount: int
    at: datetime


class PaymentsOut(BaseModel):
    enabled: bool
    message: str


class PlanOut(BaseModel):
    plan_id: str
    plan_label: str
    period_start: date
    resets_at: datetime
    quotas: list[QuotaOut]
    resumes_used: int
    resumes_limit: int
    exports_per_resume: int
    plans: list[PlanChoiceOut]
    recent: list[UsageEventOut]
    payments: PaymentsOut
    # The limits are starting points. Real ones come from measured cost.
    provisional: bool


class UpgradeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=40)


# ---- checkpoint 3.4: reports


class ReportIn(BaseModel):
    format: Literal["csv", "xlsx", "docx"]
    query: dict[str, Any] = Field(default_factory=dict)
    include_quotes: bool = False

    @field_validator("query")
    @classmethod
    def _small_query(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value)) > 8000:
            raise ValueError("The filters are too large.")
        return value


class ReportOut(BaseModel):
    id: uuid.UUID
    format: Literal["csv", "xlsx", "docx"]
    format_label: str
    ui_state: Literal["preparing", "ready", "failed"]
    size_bytes: int | None
    job_count: int | None
    criteria: list[str]
    query: dict[str, Any]
    include_quotes: bool
    error_message: str | None
    created_at: datetime
    expires_at: datetime
    download_name: str | None


# ---- checkpoint 3.5: observability (admin)


class AlertOut(BaseModel):
    key: str
    severity: Literal["critical", "warning"]
    title: str
    detail: str
    action: str
    runbook: str


class ComponentOut(BaseModel):
    name: str
    status: Literal["ok", "warning", "critical", "unknown"]
    detail: str


class RequestStatsOut(BaseModel):
    measured: bool
    window_minutes: int
    requests: int
    server_errors: int
    client_errors: int
    p50_ms: int | None
    p95_ms: int | None


class TroubleTaskOut(BaseModel):
    id: uuid.UUID
    task_type: str
    state: Literal["retrying", "stuck"]
    attempts: int
    max_attempts: int
    run_id: uuid.UUID | None
    last_error: str | None
    run_after: datetime


class SourceHealthOut(BaseModel):
    key: str
    name: str
    enabled: bool
    status: str
    breaker_open: bool
    failure_streak: int
    last_success_at: datetime | None
    last_failure_at: datetime | None


class ThresholdsOut(BaseModel):
    queue_stale_warning_seconds: int
    queue_stale_critical_seconds: int
    source_failure_streak: int
    llm_error_rate: float
    daily_spend_ceiling_usd: float
    server_error_rate: float
    p95_ms: int
    auth_failures_per_hour: int


class SecurityEventOut(BaseModel):
    action: str
    label: str
    count: int


class RateLimitOut(BaseModel):
    policy: str
    counters_over: int


class HealthOut(BaseModel):
    status: Literal["ok", "warning", "critical"]
    headline: str
    version: str
    environment: str
    generated_at: datetime
    components: list[ComponentOut]
    alerts: list[AlertOut]
    requests: RequestStatsOut
    queue_by_state: dict[str, int]
    oldest_waiting_seconds: int | None
    trouble_tasks: list[TroubleTaskOut]
    sources: list[SourceHealthOut]
    security_24h: list[SecurityEventOut]
    rate_limits_24h: list[RateLimitOut]
    thresholds: ThresholdsOut


class UsageRowOut(BaseModel):
    key: str
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class UsageOut(BaseModel):
    days: int
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    accounts: int
    average_latency_ms: int | None
    highest_account_share: float | None
    daily_spend_ceiling_usd: float
    by_model: list[UsageRowOut]
    by_purpose: list[UsageRowOut]
    by_day: list[UsageRowOut]
    by_plan: list[UsageRowOut]


class TraceTaskOut(BaseModel):
    id: uuid.UUID
    task_type: str
    state: str
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None
    owner_email: str | None


class TraceCallOut(BaseModel):
    purpose: str
    provider: str
    model: str
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    status: str
    error_class: str | None
    created_at: datetime


class TraceOut(BaseModel):
    run_id: uuid.UUID
    found: bool
    tasks: list[TraceTaskOut]
    calls: list[TraceCallOut]


# ---- checkpoint 3.6: evaluation (admin)


class EvalMetricOut(BaseModel):
    name: str
    label: str
    suite: str
    value: float
    baseline: float | None
    limit: float
    direction: Literal["higher", "lower"]
    status: Literal["ok", "regressed", "below_limit", "new"]
    delta: float | None
    cases: int
    previous: float | None = None
    change: float | None = None


class EvalFailureOut(BaseModel):
    suite: str
    case_id: str
    expected: str
    got: str
    note: str


class EvalRunOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    suite: Literal["deterministic", "llm"]
    trigger: str
    dataset_version: str
    git_sha: str | None
    model: str | None
    passed: bool
    case_count: int
    failure_count: int
    regressions: list[str]


class RankerOut(BaseModel):
    adopt: bool
    labels: int
    people: int
    reasons: list[str]


class EvalListOut(BaseModel):
    runs: list[EvalRunOut]
    latest: dict[str, EvalRunOut]
    ranker: RankerOut


class EvalSuiteOut(BaseModel):
    name: str
    cases: int
    failed: int


class EvalDetailOut(BaseModel):
    run: EvalRunOut
    versions: dict[str, str]
    metrics: list[EvalMetricOut]
    suites: list[EvalSuiteOut]
    failures: list[EvalFailureOut]
    against: EvalRunOut | None


# ---- checkpoint 3.7: your own data


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    confirm: str = Field(max_length=100)
