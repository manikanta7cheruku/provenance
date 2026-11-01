"""The source registry and the company registry: seeded from versioned files, edited by admins.

Shared reference data, so these functions use a plain session, not a tenant session. The seed files
live in registry_data/ and are the starting point. A row an administrator has changed is never
overwritten by a later seed (edited_at is set). Enabling a source follows one rule, in
pv_domain.sources.enable_blocker, and the table has the same rule as a CHECK.
"""

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_domain.company import Company
from pv_domain.sources import (
    ComplianceStatus,
    HealthStatus,
    SourceError,
    SourceRecord,
    SourceType,
    enable_blocker,
    parse_source,
)
from pv_persistence.models import CompanyRow, JobSource

# What an administrator may change. The adapter and the health fields belong to code.
ADMIN_FIELDS = (
    "enabled",
    "compliance_status",
    "terms_checked_at",
    "terms_url",
    "verification_owner",
    "rate_limit",
    "quota_policy",
    "min_poll_interval_seconds",
    "attribution_text",
    "geographic_coverage",
    "compliance_notes",
)


def _read(name: str) -> list[dict[str, Any]]:
    text = resources.files("pv_persistence").joinpath("registry_data", name).read_text("utf-8")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"{name} must hold a list")
    return data


def seed_sources() -> list[SourceRecord]:
    """The sources in the seed file, each checked by the same rules as an admin edit."""
    return [parse_source(raw) for raw in _read("sources.json")]


def seed_companies() -> list[dict[str, Any]]:
    return _read("companies.json")


def _apply(row: JobSource, record: SourceRecord) -> None:
    row.display_name = record.display_name
    row.source_type = record.source_type.value
    row.adapter = record.adapter
    row.endpoint_or_feed = record.endpoint_or_feed
    row.capabilities = dict(record.capabilities)
    row.auth_requirements = record.auth_requirements
    row.compliance_status = record.compliance_status.value
    row.terms_checked_at = record.terms_checked_at
    row.terms_url = record.terms_url
    row.verification_owner = record.verification_owner
    row.rate_limit = record.rate_limit
    row.quota_policy = record.quota_policy
    row.min_poll_interval_seconds = record.min_poll_interval_seconds
    row.attribution_text = record.attribution_text
    row.geographic_coverage = list(record.geographic_coverage)
    row.supports_user_import = record.supports_user_import
    row.enabled = record.enabled
    row.compliance_notes = record.compliance_notes
    row.updated_at = datetime.now(UTC)


def seed_registry(engine: Engine) -> tuple[int, int]:
    """Add what is missing and refresh rows nobody edited. Returns (sources, companies) written."""
    sources = seed_sources()
    written_sources = written_companies = 0
    with Session(engine) as db, db.begin():
        existing = {r.key: r for r in db.execute(select(JobSource)).scalars()}
        for record in sources:
            row = existing.get(record.key)
            if row is None:
                row = JobSource(key=record.key)
                _apply(row, record)
                db.add(row)
                written_sources += 1
            elif row.edited_at is None:
                _apply(row, record)
                written_sources += 1
        known = {r.key: r for r in db.execute(select(CompanyRow)).scalars()}
        for raw in seed_companies():
            company = known.get(raw["key"])
            last = (
                date.fromisoformat(raw["last_verified_at"]) if raw.get("last_verified_at") else None
            )
            if company is None:
                company = CompanyRow(key=raw["key"])
                db.add(company)
            elif company.edited_at is not None:
                continue
            company.canonical_name = raw["canonical_name"]
            company.aliases = list(raw.get("aliases", []))
            company.domain = raw.get("domain")
            company.career_url = raw.get("career_url")
            company.ats_platform = raw.get("ats_platform")
            company.ats_board_id = raw.get("ats_board_id")
            company.industry = raw.get("industry")
            company.country = raw.get("country")
            company.last_verified_at = last
            written_companies += 1
    return written_sources, written_companies


def to_record(row: JobSource) -> SourceRecord:
    return SourceRecord(
        key=row.key,
        display_name=row.display_name,
        source_type=SourceType(row.source_type),
        adapter=row.adapter,
        endpoint_or_feed=row.endpoint_or_feed,
        capabilities=dict(row.capabilities),
        auth_requirements=row.auth_requirements,
        compliance_status=ComplianceStatus(row.compliance_status),
        terms_checked_at=row.terms_checked_at,
        terms_url=row.terms_url,
        verification_owner=row.verification_owner,
        rate_limit=row.rate_limit,
        quota_policy=row.quota_policy,
        min_poll_interval_seconds=row.min_poll_interval_seconds,
        attribution_text=row.attribution_text,
        geographic_coverage=tuple(row.geographic_coverage),
        enabled=row.enabled,
        compliance_notes=row.compliance_notes,
        supports_user_import=row.supports_user_import,
        health_status=HealthStatus(row.health_status),
    )


def list_source_rows(db: Session) -> list[JobSource]:
    return list(db.execute(select(JobSource).order_by(JobSource.display_name)).scalars())


def list_sources(db: Session) -> list[SourceRecord]:
    return [to_record(r) for r in list_source_rows(db)]


def get_source_row(db: Session, key: str) -> JobSource | None:
    return db.get(JobSource, key)


def list_companies(db: Session) -> list[Company]:
    return [
        Company(
            key=r.key,
            canonical_name=r.canonical_name,
            aliases=tuple(r.aliases),
            domain=r.domain,
            career_url=r.career_url,
            ats_platform=r.ats_platform,
            ats_board_id=r.ats_board_id,
            industry=r.industry,
            country=r.country,
            last_verified_at=r.last_verified_at.isoformat() if r.last_verified_at else None,
        )
        for r in db.execute(select(CompanyRow).order_by(CompanyRow.canonical_name)).scalars()
    ]


def record_as_dict(record: SourceRecord) -> dict[str, Any]:
    data = asdict(record)
    data["source_type"] = record.source_type.value
    data["compliance_status"] = record.compliance_status.value
    data["terms_checked_at"] = (
        record.terms_checked_at.isoformat() if record.terms_checked_at else None
    )
    data["geographic_coverage"] = list(record.geographic_coverage)
    data.pop("extra", None)
    data.pop("health_status", None)
    return data


def update_source(
    db: Session, row: JobSource, patch: dict[str, Any], today: date, window_days: int
) -> JobSource:
    """Apply an administrator change. The result must pass every rule, or SourceError says where."""
    merged = record_as_dict(to_record(row))
    for name, value in patch.items():
        if name not in ADMIN_FIELDS:
            raise SourceError({name: "This field cannot be changed here."})
        merged[name] = value
    record = parse_source(merged)
    if record.enabled and (reason := enable_blocker(record, today, window_days)):
        raise SourceError({"enabled": f"It cannot be enabled. {reason}"})
    _apply(row, record)
    row.edited_at = datetime.now(UTC)
    return row
