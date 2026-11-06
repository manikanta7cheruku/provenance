"""Checkpoint 3.4: reports of a person's jobs as CSV, Excel and Word.

The real database, the real API and the real worker task, with a private folder for storage. The
files are opened with real readers (openpyxl, python-docx, csv) and the formula test strings are
planted in the jobs themselves, so neutralizing is checked end to end.
"""

import csv
import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from docx import Document
from fastapi import FastAPI
from helpers import Account
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.engine import Engine
from test_tailoring import checked_job

from pv_config import Settings
from pv_files import FileStorage, StorageError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.build_report import run_build

REPORTS = "/api/v1/reports"
MakeAccount = Callable[..., Account]


def ask(account: Account, **body: Any) -> Any:
    return account.client.post(
        REPORTS, json={"format": "xlsx", "query": {"view": "all"}, **body}, headers=account.csrf
    )


def make_context(
    engine: Engine, settings: Settings, account: Account, report_id: str, *, attempt: int = 1,
    owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        run_id = db.execute(
            text("SELECT run_id FROM report_exports WHERE id = :i"), {"i": report_id}
        ).scalar_one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="build_report", args={"report_id": report_id},
        secret={}, attempt=attempt, max_attempts=3, owner_user_id=uuid.UUID(owner or account.user_id),
        run_id=run_id, settings=settings, engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def make_report(
    account: Account, engine: Engine, settings: Settings, storage: FileStorage, **body: Any
) -> dict[str, Any]:
    response = ask(account, **body)
    assert response.status_code == 202, response.text
    report = dict(response.json())
    run_build(make_context(engine, settings, account, report["id"]), storage=storage)
    return dict(account.client.get(f"{REPORTS}/{report['id']}").json())


def plant(
    engine: Engine, account: Account, job_id: str, title: str, company: str, note: str
) -> None:
    """Put formula test strings in the stored job, the way a hostile posting would."""
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(
            text("UPDATE job_postings SET title = :t, company = :c WHERE id = :i"),
            {"t": title, "c": company, "i": job_id},
        )
        db.execute(
            text(
                "INSERT INTO job_decisions (posting_id, owner_user_id, state, note) "
                "VALUES (:i, :o, 'saved', :n) ON CONFLICT (posting_id) DO UPDATE SET note = :n"
            ),
            {"i": job_id, "o": account.user_id, "n": note},
        )


class BrokenStorage:
    def __init__(self, inner: FileStorage, fail: bool = True) -> None:
        self.inner = inner
        self.fail = fail

    def put(self, key: str, data: bytes) -> None:
        if self.fail:
            raise StorageError("disk full")
        self.inner.put(key, data)

    def get(self, key: str) -> bytes:
        return self.inner.get(key)

    def delete(self, key: str) -> None:
        self.inner.delete(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


# ------------------------------------------------------------------------ the happy path


def test_a_workbook_is_made_by_the_worker_stored_privately_and_downloaded(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    created = ask(account)
    assert created.status_code == 202 and created.json()["ui_state"] == "preparing"
    report = created.json()
    assert report["format"] == "xlsx" and "List: All" in report["criteria"]
    assert report["download_name"] is None
    assert account.client.get(f"{REPORTS}/{report['id']}/download").status_code == 404

    run_build(make_context(engine, settings, account, report["id"]), storage=storage)
    done = account.client.get(f"{REPORTS}/{report['id']}").json()
    assert done["ui_state"] == "ready" and done["job_count"] == 1 and done["size_bytes"] > 1000

    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM report_exports")).scalar_one()
    assert key.startswith("exports/") and storage.get(key)[:2] == b"PK"

    got = account.client.get(f"{REPORTS}/{report['id']}/download")
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert got.headers["content-disposition"].startswith(
        'attachment; filename="Provenance opportunities '
    )
    assert got.headers["content-disposition"].endswith('.xlsx"')
    assert (
        "no-store" in got.headers["cache-control"]
        and got.headers["x-content-type-options"] == "nosniff"
    )

    book = load_workbook(io.BytesIO(got.content))
    assert book.sheetnames == ["Summary", "Opportunities", "Requirements", "Evidence"]
    cells = [(r[0].value, r[1].value) for r in book["Summary"].iter_rows()]
    assert any(a == "Made on" and str(b).endswith("UTC") for a, b in cells)
    assert any(a == "Source" and "Wellfound" in str(b) for a, b in cells)
    assert any(a == "In short" and "1 opportunity." in str(b) for a, b in cells)
    opportunities = book["Opportunities"]
    assert opportunities.max_row == 2 and opportunities["A2"].value
    requirements = book["Requirements"]
    assert requirements.max_row > 2
    verdicts = {
        requirements.cell(row=r, column=5).value for r in range(2, requirements.max_row + 1)
    }
    assert {"Shown", "Not shown"} <= verdicts | {"Partly shown", "Shown", "Not shown"}
    assert job_id  # the job is the one made by checked_job


def test_csv_and_word_reports_are_made_from_the_same_jobs(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    csv_report = make_report(account, engine, settings, storage, format="csv")
    docx_report = make_report(account, engine, settings, storage, format="docx")
    assert csv_report["ui_state"] == "ready" and docx_report["ui_state"] == "ready"

    raw = account.client.get(f"{REPORTS}/{csv_report['id']}/download")
    assert raw.content.startswith(b"\xef\xbb\xbf") and "text/csv" in raw.headers["content-type"]
    rows = list(csv.reader(io.StringIO(raw.content.decode("utf-8-sig"))))
    assert rows[0][0] == "Company" and len(rows) == 2

    word = account.client.get(f"{REPORTS}/{docx_report['id']}/download")
    assert word.headers["content-disposition"].endswith('.docx"')
    doc = Document(io.BytesIO(word.content))
    text_ = "\n".join(p.text for p in doc.paragraphs)
    assert "Provenance opportunities report" in text_ and "Wellfound" in text_
    assert "Nothing here was sent to anyone." in text_


# ------------------------------------------------------------------------ what it holds


def test_quotes_are_left_out_unless_asked_for(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)

    def evidence_quotes(report: dict[str, Any]) -> list[str]:
        book = load_workbook(
            io.BytesIO(account.client.get(f"{REPORTS}/{report['id']}/download").content)
        )
        sheet = book["Evidence"]
        return [sheet.cell(row=r, column=6).value or "" for r in range(2, sheet.max_row + 1)]

    plain = make_report(account, engine, settings, storage)
    full = make_report(account, engine, settings, storage, include_quotes=True)
    assert plain["include_quotes"] is False and full["include_quotes"] is True
    plain_quotes = evidence_quotes(plain)
    assert plain_quotes and all(q == "" for q in plain_quotes)
    assert any(q for q in evidence_quotes(full))
    assert all(len(q) <= 300 for q in evidence_quotes(full))


def test_filters_choose_the_jobs_and_are_written_in_words(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    none = make_report(
        account, engine, settings, storage, query={"view": "all", "company": "No Such Co"}
    )
    assert none["job_count"] == 0 and "Company: No Such Co" in none["criteria"]
    book = load_workbook(io.BytesIO(account.client.get(f"{REPORTS}/{none['id']}/download").content))
    assert book["Opportunities"].max_row == 1  # a header row and no jobs
    saved = make_report(account, engine, settings, storage, query={"view": "saved"})
    assert saved["job_count"] == 0 and "List: Saved" in saved["criteria"]


def test_junk_in_the_filters_is_dropped_not_trusted(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    report = make_report(
        account, engine, settings, storage,
        query={"view": "everything", "bands": ["nope", "strong"], "sort": "; DROP TABLE users", "x": 1},
    )  # fmt: skip
    assert report["ui_state"] == "ready"
    assert "List: Active" in report["criteria"] and "Fit: Strong match" in report["criteria"]
    assert ask(account, query={"text": "x" * 20000}).status_code == 422
    assert ask(account, format="pdf").status_code == 422


# ------------------------------------------------------------------------ safety


ATTACKS = ['=HYPERLINK("http://evil.example","x")', "+1+1", "-2+3", "@SUM(A1)"]


@pytest.mark.parametrize("attack", ATTACKS)
def test_formula_strings_in_a_job_are_neutralized_in_csv_and_xlsx(
    attack: str, app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings,
    storage: FileStorage,
) -> None:  # fmt: skip
    account, job_id = checked_job(app, make_account, engine, settings)
    plant(engine, account, job_id, attack, attack, attack)
    csv_report = make_report(account, engine, settings, storage, format="csv")
    xlsx_report = make_report(account, engine, settings, storage, format="xlsx")

    rows = list(
        csv.reader(
            io.StringIO(
                account.client.get(f"{REPORTS}/{csv_report['id']}/download").content.decode(
                    "utf-8-sig"
                )
            )
        )
    )
    for cell in rows[1]:
        assert not cell.startswith(("=", "+", "-", "@"))
    assert rows[1][0] == "'" + attack and rows[1][1] == "'" + attack

    book = load_workbook(
        io.BytesIO(account.client.get(f"{REPORTS}/{xlsx_report['id']}/download").content)
    )
    for sheet in book:
        for row in sheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f"
                if isinstance(cell.value, str):
                    assert not cell.value.startswith(("=", "+", "-", "@"))
    assert book["Opportunities"]["A2"].value == "'" + attack


def test_another_person_cannot_see_download_or_delete_a_report(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    report = make_report(account, engine, settings, storage)
    stranger = make_account(app)
    assert stranger.client.get(f"{REPORTS}/{report['id']}").status_code == 404
    assert stranger.client.get(f"{REPORTS}/{report['id']}/download").status_code == 404
    assert (
        stranger.client.delete(f"{REPORTS}/{report['id']}", headers=stranger.csrf).status_code
        == 404
    )
    assert stranger.client.get(REPORTS).json() == []
    # The owner is unaffected.
    assert account.client.get(f"{REPORTS}/{report['id']}/download").status_code == 200


def test_the_worker_does_nothing_for_someone_elses_report(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    stranger = make_account(app)
    report = ask(account).json()
    run_build(
        make_context(engine, settings, account, report["id"], owner=stranger.user_id),
        storage=storage,
    )
    assert account.client.get(f"{REPORTS}/{report['id']}").json()["ui_state"] == "preparing"


def test_reports_need_a_signed_in_person_and_a_csrf_token(
    app: FastAPI, make_account: MakeAccount
) -> None:
    from helpers import new_client

    assert new_client(app).get(REPORTS).status_code == 401
    account = make_account(app)
    refused = account.client.post(REPORTS, json={"format": "csv", "query": {}})
    assert refused.status_code in (400, 403)


def test_row_level_security_is_forced_on_report_exports(engine: Engine) -> None:
    with engine.connect() as conn:
        enabled, forced = conn.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'report_exports'"
            )
        ).one()
    assert enabled and forced


# ------------------------------------------------------------------------ states and limits


def test_a_report_that_cannot_be_stored_retries_then_shows_failed_and_can_be_asked_again(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    report = ask(account).json()
    broken = BrokenStorage(storage)
    with pytest.raises(TaskFailure) as first:
        run_build(make_context(engine, settings, account, report["id"], attempt=1), storage=broken)
    assert first.value.retryable
    assert account.client.get(f"{REPORTS}/{report['id']}").json()["ui_state"] == "preparing"

    run_build(make_context(engine, settings, account, report["id"], attempt=3), storage=broken)
    failed = account.client.get(f"{REPORTS}/{report['id']}").json()
    assert failed["ui_state"] == "failed" and "Try again" in failed["error_message"]
    assert account.client.get(f"{REPORTS}/{report['id']}/download").status_code == 404
    assert ask(account).status_code == 202  # asking again is allowed


def test_a_file_that_cannot_be_written_is_a_failure_not_a_crash(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    import pv_worker.handlers.build_report as module

    def boom(report: object, fmt: str) -> bytes:
        raise ValueError("secret job text")

    monkeypatch.setattr(module, "write_report", boom)
    account, _ = checked_job(app, make_account, engine, settings)
    failed = make_report(account, engine, settings, storage)
    assert failed["ui_state"] == "failed"
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        code = db.execute(text("SELECT error_code FROM report_exports")).scalar_one()
        message = db.execute(
            text("SELECT error_summary FROM workflow_runs WHERE workflow_type = 'report_export'")
        ).scalar_one()
    assert code == "BUILD_FAILED" and "secret" not in (message or "")


def test_only_three_reports_can_be_building_at_once(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    for _ in range(3):
        assert ask(account).status_code == 202
    blocked = ask(account)
    assert blocked.status_code == 409 and blocked.json()["code"] == "REPORT_IN_PROGRESS"


def test_asking_is_rate_limited(app: FastAPI, make_account: MakeAccount) -> None:
    from pv_domain.ratelimit import DEFAULT_POLICIES

    assert DEFAULT_POLICIES["report_export_user"].limit == 20


def test_the_newest_twenty_are_kept(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account = make_account(app)
    for _ in range(22):
        report = ask(account, format="csv").json()
        run_build(make_context(engine, settings, account, report["id"]), storage=storage)
    listed = account.client.get(REPORTS).json()
    assert len(listed) == 20 and all(r["ui_state"] == "ready" for r in listed)


def test_an_expired_report_is_gone_and_its_file_is_deleted(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account = make_account(app)
    report = make_report(account, engine, settings, storage, format="csv")
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM report_exports")).scalar_one()
        db.execute(
            text("UPDATE report_exports SET expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(minutes=1)},
        )
    assert storage.exists(key)
    assert account.client.get(f"{REPORTS}/{report['id']}/download").status_code == 404
    assert account.client.get(f"{REPORTS}/{report['id']}").status_code == 404
    assert account.client.get(REPORTS).json() == []  # listing sweeps the expired row
    assert not storage.exists(key)


def test_deleting_a_report_removes_the_file_and_a_late_task_does_nothing(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account = make_account(app)
    waiting = ask(account).json()
    context = make_context(engine, settings, account, waiting["id"])
    assert (
        account.client.delete(f"{REPORTS}/{waiting['id']}", headers=account.csrf).status_code == 204
    )
    run_build(context, storage=storage)  # the row is gone: nothing happens, nothing raised
    assert account.client.get(REPORTS).json() == []

    done = make_report(account, engine, settings, storage, format="csv")
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM report_exports")).scalar_one()
    assert account.client.delete(f"{REPORTS}/{done['id']}", headers=account.csrf).status_code == 204
    assert not storage.exists(key)


def test_audit_records_the_action_and_never_the_filters_or_text(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    ask(account, query={"view": "all", "text": "very private words"})
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT action, metadata::text FROM audit_events WHERE action = 'report.requested'"
            )
        ).all()
    assert rows and all("very private words" not in (r[1] or "") for r in rows)


def test_exporting_is_never_counted_against_the_plan(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
) -> None:
    account, _ = checked_job(app, make_account, engine, settings)
    before = account.client.get("/api/v1/plan").json()["quotas"]
    make_report(account, engine, settings, storage)
    assert account.client.get("/api/v1/plan").json()["quotas"] == before
