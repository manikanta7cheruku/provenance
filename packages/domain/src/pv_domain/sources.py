"""The source registry as data and rules: what a job source is, what it can do, and when it may be used.

A source is where jobs can come from: an employer's ATS board, a job API, a public feed, a company
career site, or "user import only" for platforms with no permitted automated access. Capabilities are
never assumed to be the same across sources, and a source may be used only while its compliance
record says so. The record carries where its terms were read, when, and by whom, and it expires.

Pure code. The database, the admin routes and the resolver all use these rules.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class SourceType(StrEnum):
    ATS_BOARD = "ats_board"
    JOB_API = "job_api"
    PUBLIC_FEED = "public_feed"
    COMPANY_CAREERS = "company_careers"
    USER_IMPORT_ONLY = "user_import_only"


class ComplianceStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class HealthStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


CAPABILITIES = (
    "can_search",
    "can_enumerate",
    "supports_full_description",
    "supports_company_filter",
    "supports_location_filter",
    "requires_auth",
    "requires_attribution",
)

DEFAULT_REVIEW_WINDOW_DAYS = 180
MAX_TEXT = 2000


@dataclass(frozen=True)
class SourceRecord:
    key: str
    display_name: str
    source_type: SourceType
    adapter: str | None
    endpoint_or_feed: str | None
    capabilities: dict[str, bool]
    auth_requirements: str
    compliance_status: ComplianceStatus
    terms_checked_at: date | None
    terms_url: str | None
    verification_owner: str | None
    rate_limit: str
    quota_policy: str
    min_poll_interval_seconds: int
    attribution_text: str
    geographic_coverage: tuple[str, ...]
    enabled: bool
    compliance_notes: str
    supports_user_import: bool = True
    health_status: HealthStatus = HealthStatus.UNKNOWN
    extra: dict[str, Any] = field(default_factory=dict)

    def can(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability, False))


class SourceError(ValueError):
    def __init__(self, problems: dict[str, str]) -> None:
        super().__init__("; ".join(problems.values()))
        self.problems = problems


def review_expired(terms_checked_at: date | None, today: date, window_days: int) -> bool:
    """True when the terms were never checked or were last checked longer ago than the window."""
    if terms_checked_at is None:
        return True
    return (today - terms_checked_at).days > window_days


def enable_blocker(
    record: SourceRecord, today: date, window_days: int = DEFAULT_REVIEW_WINDOW_DAYS
) -> str | None:
    """The reason a source cannot be turned on, or None when it can. The one rule for enabling."""
    if record.compliance_status != ComplianceStatus.VERIFIED:
        return f"Its compliance status is {record.compliance_status.value}, not verified."
    if not record.terms_url or not record.verification_owner:
        return "The record has no terms address or no reviewer."
    if review_expired(record.terms_checked_at, today, window_days):
        return f"Its terms were not checked in the last {window_days} days."
    if record.source_type == SourceType.USER_IMPORT_ONLY:
        return "This platform is import only. There is nothing to enable."
    return None


def unavailable_reason(
    record: SourceRecord, today: date, window_days: int = DEFAULT_REVIEW_WINDOW_DAYS
) -> str | None:
    """Why a source cannot be used for automated search right now, in words for a person."""
    if record.source_type == SourceType.USER_IMPORT_ONLY:
        return "Automated access to this platform is not permitted, so jobs from it are imported by you."
    if record.compliance_status == ComplianceStatus.PROHIBITED:
        return "Its terms do not allow automated access."
    if record.compliance_status == ComplianceStatus.RESTRICTED:
        return "Its terms restrict how its jobs may be used, and that review is not settled."
    if record.compliance_status == ComplianceStatus.UNVERIFIED:
        return "Its terms have not been verified yet."
    if review_expired(record.terms_checked_at, today, window_days):
        return "The review of its terms has expired."
    if not record.enabled:
        return "It is switched off."
    return None


def adapter_ready(record: SourceRecord) -> bool:
    """Whether code exists to fetch from this source. Adapters arrive in checkpoint 2.6."""
    return record.adapter is not None


# ---- reading a seed or an admin edit


def _text(
    raw: dict[str, Any], key: str, problems: dict[str, str], *, required: bool = False
) -> str:
    value = raw.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        problems[key] = "This should be text."
        return ""
    value = value.strip()
    if required and not value:
        problems[key] = "This is required."
    value = str(value)
    if len(value) > MAX_TEXT:
        problems[key] = f"Keep this under {MAX_TEXT} characters."
        return value[:MAX_TEXT]
    return value


def parse_source(raw: Any) -> SourceRecord:
    """A source from a seed file or an admin edit, or SourceError saying what is wrong and where."""
    if not isinstance(raw, dict):
        raise SourceError({"source": "A source must be an object."})
    problems: dict[str, str] = {}
    key = _text(raw, "key", problems, required=True)
    if key and not key.replace("_", "").replace("-", "").isalnum():
        problems["key"] = "Use letters, numbers, hyphens and underscores."
    try:
        source_type = SourceType(str(raw.get("source_type")))
    except ValueError:
        problems["source_type"] = "Choose a known source type."
        source_type = SourceType.USER_IMPORT_ONLY
    try:
        status = ComplianceStatus(raw.get("compliance_status", "unverified"))
    except ValueError:
        problems["compliance_status"] = "Choose a known compliance status."
        status = ComplianceStatus.UNVERIFIED
    caps_raw = raw.get("capabilities", {})
    caps: dict[str, bool] = {}
    if not isinstance(caps_raw, dict):
        problems["capabilities"] = "Capabilities must be an object."
    else:
        for name in CAPABILITIES:
            value = caps_raw.get(name, False)
            if not isinstance(value, bool):
                problems[f"capabilities.{name}"] = "This must be true or false."
            caps[name] = value is True
        for name in caps_raw:
            if name not in CAPABILITIES:
                problems[f"capabilities.{name}"] = "That capability is not known."
    checked: date | None = None
    if raw.get("terms_checked_at"):
        try:
            checked = date.fromisoformat(str(raw["terms_checked_at"]))
        except ValueError:
            problems["terms_checked_at"] = "Use a date like 2026-11-02."
    interval = raw.get("min_poll_interval_seconds", 3600)
    if isinstance(interval, bool) or not isinstance(interval, int) or interval < 0:
        problems["min_poll_interval_seconds"] = "Use a whole number of seconds, zero or more."
        interval = 3600
    coverage = raw.get("geographic_coverage", [])
    if not isinstance(coverage, list) or not all(isinstance(c, str) for c in coverage):
        problems["geographic_coverage"] = "Use a list of country names."
        coverage = []
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        problems["enabled"] = "This must be true or false."
        enabled = False
    record = SourceRecord(
        key=key,
        display_name=_text(raw, "display_name", problems, required=True),
        source_type=source_type,
        adapter=_text(raw, "adapter", problems) or None,
        endpoint_or_feed=_text(raw, "endpoint_or_feed", problems) or None,
        capabilities=caps,
        auth_requirements=_text(raw, "auth_requirements", problems) or "None",
        compliance_status=status,
        terms_checked_at=checked,
        terms_url=_text(raw, "terms_url", problems) or None,
        verification_owner=_text(raw, "verification_owner", problems) or None,
        rate_limit=_text(raw, "rate_limit", problems),
        quota_policy=_text(raw, "quota_policy", problems),
        min_poll_interval_seconds=interval,
        attribution_text=_text(raw, "attribution_text", problems),
        geographic_coverage=tuple(c.strip() for c in coverage if c.strip()),
        enabled=enabled,
        compliance_notes=_text(raw, "compliance_notes", problems),
        supports_user_import=raw.get("supports_user_import", True) is not False,
    )
    if record.can("requires_attribution") and not record.attribution_text:
        problems["attribution_text"] = (
            "A source that requires attribution needs its attribution text."
        )
    if source_type == SourceType.USER_IMPORT_ONLY and (record.adapter or record.can("can_search")):
        problems["adapter"] = "An import only platform has no adapter and cannot be searched."
    if record.enabled and (reason := enable_blocker(record, date.today())):
        problems["enabled"] = f"It cannot be enabled. {reason}"
    if problems:
        raise SourceError(problems)
    return record
