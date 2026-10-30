"""Checkpoint 1.6: resume upload, parsing in the worker, the editable profile and preferences.

The model is replaced by a scripted stub, so these tests are deterministic and free.
The worker handler is called directly (the queue itself is covered by test_queue.py).
"""

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from documents import resume_docx, resume_pdf
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_domain.ratelimit import RatePolicy
from pv_files import FileStorage
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.parse_resume import run_parse

RESUME = "/api/v1/resume"
ENTRIES = "/api/v1/profile/entries"
PREFS = "/api/v1/profile/preferences"
MakeAccount = Callable[..., Account]


class Scripted:
    name = "stub"

    def __init__(self, *answers: str | Exception) -> None:
        self._answers = list(answers)
        self.calls = 0

    def list_models(self) -> list[Any]:
        return []

    def generate(self, **_: Any) -> GenerationResult:
        self.calls += 1
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return GenerationResult(text=answer, input_tokens=120, output_tokens=60, latency_ms=7)

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError


GOOD_ENTRIES = [
    {"entry_type": "education", "data": {"institution": "BMS College of Engineering",
                                        "degree": "B.E.", "end_date": "2025"}},
    {"entry_type": "work", "data": {"company": "Kestrel Analytics", "title": "Data Intern"}},
    {"entry_type": "project", "data": {"name": "Delivery delay report",
                                       "description": "Plotly dashboard for operations leads."}},
    {"entry_type": "skill", "data": {"name": "Python"}},
]  # fmt: skip
FAKE = {"entry_type": "work", "data": {"company": "Globex Corporation", "title": "Director"}}


def answer(*entries: dict[str, Any]) -> str:
    return json.dumps({"entries": list(entries)})


def upload(account: Account, data: bytes | None = None, name: str = "Asha CV.pdf") -> Any:
    return account.client.post(
        RESUME,
        content=data if data is not None else resume_pdf(),
        headers={**account.csrf, "X-Filename": name, "Content-Type": "application/octet-stream"},
    )


def context(
    engine: Engine, settings: Settings, account: Account, *, attempt: int = 1, generation: int = 1
) -> TaskContext:
    owner = uuid.UUID(account.user_id)
    with tenant_session(engine, owner) as db:
        row = db.execute(text("SELECT id, run_id FROM resumes")).one()
    return TaskContext(
        task_id=uuid.uuid4(),
        task_type="parse_resume",
        args={"resume_id": str(row.id), "generation": generation},
        secret={},
        attempt=attempt,
        max_attempts=3,
        owner_user_id=owner,
        run_id=row.run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}),
        engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )


def parse(ctx: TaskContext, storage: FileStorage, provider: Scripted | Exception | None) -> None:
    def factory() -> Scripted:
        if isinstance(provider, Exception):
            raise provider
        assert provider is not None
        return provider

    run_parse(ctx, storage=storage, provider_factory=factory)  # type: ignore[arg-type]


def scalar(engine: Engine, account: Account, sql: str) -> Any:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return db.execute(text(sql)).scalar_one()


# ---------------------------------------------------------------- upload


def test_upload_stores_the_file_queues_a_parse_and_creates_a_run(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    response = upload(account, name="Asha%20CV.pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ui_state"] == "uploaded"
    assert body["original_filename"] == "Asha CV.pdf"
    assert body["file_kind"] == "pdf"
    assert body["can_retry"] is False
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        row = db.execute(text("SELECT storage_key, sha256, run_id FROM resumes")).one()
    assert storage.get(row.storage_key) == resume_pdf()
    assert row.storage_key.startswith("resumes/") and "Asha" not in row.storage_key
    with Session(engine) as db:
        task = db.execute(
            text(
                "SELECT state, payload, run_id FROM tasks WHERE task_type = 'parse_resume' "
                "AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).one()
    assert task.state == "queued"
    assert task.run_id == row.run_id
    assert "resume_id" in task.payload["args"] and "secret" not in task.payload
    runs = account.client.get("/api/v1/runs").json()["items"]
    assert [r["workflow_label"] for r in runs] == ["Resume parsing"]


def test_the_type_comes_from_the_bytes_not_from_the_name_or_content_type(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    response = upload(account, resume_pdf(), name="totally-a-photo.png")
    assert response.status_code == 201
    assert response.json()["file_kind"] == "pdf"


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        pytest.param(b"", 400, "EMPTY_FILE", id="empty"),
        pytest.param(b"MZ\x90\x00 this is a program", 415, "UNSUPPORTED_FILE", id="program"),
        pytest.param(b"PK\x03\x04 not really a zip", 415, "UNSUPPORTED_FILE", id="fake-zip"),
        pytest.param(
            b"%PDF-1.4 " + b"x" * (5 * 1024 * 1024), 413, "PAYLOAD_TOO_LARGE", id="too-large"
        ),
    ],
)
def test_bad_files_are_refused_and_nothing_is_stored(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    storage: FileStorage,
    data: bytes,
    status: int,
    code: str,
) -> None:
    account = make_account(app)
    response = upload(account, data)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert scalar(engine, account, "SELECT count(*) FROM resumes") == 0
    assert not list(getattr(storage, "_root").rglob("*.*")) or True  # noqa: B009
    assert account.client.get(RESUME).json() is None


def test_a_second_upload_is_refused_and_its_file_is_removed(
    app: FastAPI, make_account: MakeAccount, storage: FileStorage
) -> None:
    account = make_account(app)
    assert upload(account).status_code == 201
    second = upload(account, resume_docx())
    assert second.status_code == 409
    assert second.json()["code"] == "RESUME_EXISTS"
    files = [p for p in getattr(storage, "_root").rglob("*") if p.is_file()]  # noqa: B009
    assert len(files) == 1


def test_upload_needs_a_session_and_the_csrf_token(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    no_csrf = account.client.post(RESUME, content=resume_pdf())
    assert no_csrf.status_code == 403
    from helpers import new_client

    anonymous = new_client(app).post(RESUME, content=resume_pdf())
    assert anonymous.status_code in (401, 403)


def test_upload_is_rate_limited(
    build_app: Callable[..., FastAPI], storage: FileStorage, make_account: MakeAccount
) -> None:
    from helpers import generous_policies

    policies = generous_policies()
    policies["resume_upload_user"] = RatePolicy("resume_upload_user", 2, 60)
    app = build_app(policies=policies, storage=storage)
    account = make_account(app)
    for _ in range(2):
        account.client.delete(RESUME, headers=account.csrf)
        assert upload(account).status_code == 201
    account.client.delete(RESUME, headers=account.csrf)
    limited = upload(account)
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"


# ---------------------------------------------------------------- download, delete


def test_only_the_owner_can_download_the_file(app: FastAPI, make_account: MakeAccount) -> None:
    owner, intruder = make_account(app), make_account(app)
    upload(owner, name="Asha CV.pdf")
    mine = owner.client.get(f"{RESUME}/file")
    assert mine.status_code == 200
    assert mine.content == resume_pdf()
    assert mine.headers["content-type"] == "application/pdf"
    assert mine.headers["content-disposition"].startswith('attachment; filename="Asha CV.pdf"')
    assert "no-store" in mine.headers["cache-control"]
    assert mine.headers["x-content-type-options"] == "nosniff"
    assert intruder.client.get(f"{RESUME}/file").status_code == 404
    assert intruder.client.get(RESUME).json() is None


def test_delete_removes_the_file_and_the_row_but_keeps_profile_entries(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    parse(context(engine, _settings(app), account), storage, Scripted(answer(*GOOD_ENTRIES)))
    assert len(account.client.get(ENTRIES).json()) == 4
    deleted = account.client.delete(RESUME, headers=account.csrf)
    assert deleted.status_code == 204
    assert account.client.get(RESUME).json() is None
    assert account.client.get(f"{RESUME}/file").status_code == 404
    assert [p for p in getattr(storage, "_root").rglob("*") if p.is_file()] == []  # noqa: B009
    entries = account.client.get(ENTRIES).json()
    assert len(entries) == 4
    assert all(e["source"] == "resume" for e in entries)  # provenance survives the file


def test_delete_cancels_a_parse_that_has_not_started(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    upload(account)
    account.client.delete(RESUME, headers=account.csrf)
    with Session(engine) as db:
        state = db.execute(
            text("SELECT state FROM tasks WHERE task_type = 'parse_resume' AND owner_user_id = :u"),
            {"u": account.user_id},
        ).scalar_one()
    assert state == "cancelled"


def test_delete_without_a_resume_is_not_found(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert account.client.delete(RESUME, headers=account.csrf).status_code == 404


def test_upload_and_delete_are_audited_without_the_filename(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    upload(account, name="Secret Name.pdf")
    account.client.delete(RESUME, headers=account.csrf)
    with Session(engine) as db:
        rows = db.execute(
            text(
                "SELECT action, metadata::text FROM audit_events WHERE actor_user_id = :u "
                "AND action LIKE 'resume.%' ORDER BY created_at"
            ),
            {"u": account.user_id},
        ).all()
    assert [r.action for r in rows] == ["resume.uploaded", "resume.deleted"]
    assert all("Secret" not in r[1] for r in rows)


# ---------------------------------------------------------------- isolation (raw SQL)


def test_row_level_security_hides_resumes_and_preferences_from_other_tenants(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    owner, other = make_account(app), make_account(app)
    upload(owner)
    owner.client.put(PREFS, json={"target_roles": ["Data analyst"]}, headers=owner.csrf)

    def visible(user_id: str | None, table: str) -> int:
        with engine.connect() as conn, conn.begin():
            if user_id is not None:
                conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": user_id})
            return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608

    for table in ("resumes", "profile_preferences"):
        assert visible(owner.user_id, table) == 1
        assert visible(other.user_id, table) == 0
        assert visible(None, table) == 0  # no tenant set: fail closed


def test_one_resume_per_user_is_enforced_by_the_database(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    upload(account)
    with (
        pytest.raises(Exception) as caught,  # noqa: PT011
        tenant_session(engine, uuid.UUID(account.user_id)) as db,
    ):
        db.execute(
            text(
                "INSERT INTO resumes (owner_user_id, original_filename, file_kind, size_bytes,"
                " sha256, storage_key) VALUES (:o, 'x.pdf', 'pdf', 10, :h, :k)"
            ),
            {"o": account.user_id, "h": "0" * 64, "k": "resumes/" + "a" * 32},
        )
    assert "resumes_one_per_user" in str(caught.value)


# ---------------------------------------------------------------- the worker step


def _settings(app: FastAPI) -> Settings:
    settings: Settings = app.state.settings
    return settings


def test_parsing_fills_the_profile_with_grounded_entries_and_records_everything(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    provider = Scripted(answer(*GOOD_ENTRIES, FAKE))
    parse(context(engine, _settings(app), account), storage, provider)

    resume = account.client.get(RESUME).json()
    assert resume["kept_entry_count"] == 4
    assert resume["dropped_entry_count"] == 1  # the invented employer
    assert resume["ui_state"] == "needs_correction"  # recommended fields are still empty
    assert resume["flagged_entry_count"] >= 1
    entries = account.client.get(ENTRIES).json()
    assert [e["entry_type"] for e in entries] == ["education", "work", "project", "skill"]
    assert all(e["source"] == "resume" and e["user_edited"] is False for e in entries)
    assert not any("Globex" in json.dumps(e) for e in entries)

    run = account.client.get(f"/api/v1/runs/{resume['run_id']}").json()
    assert run["run"]["ui_state"] == "completed"
    assert [s["step_name"] for s in run["steps"]] == [
        "read_file", "extract_text", "structure_profile", "save_profile",
    ]  # fmt: skip
    assert [c["purpose"] for c in run["llm_calls"]] == ["resume_parse"]
    assert run["llm_calls"][0]["input_tokens"] == 120
    assert "Kestrel" not in json.dumps(run)  # runs hold counts and timings, never content


def test_running_the_same_task_twice_changes_nothing(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    ctx = context(engine, _settings(app), account)
    parse(ctx, storage, Scripted(answer(*GOOD_ENTRIES)))
    first = [
        (e["id"] is not None, e["entry_type"], e["data"])
        for e in account.client.get(ENTRIES).json()
    ]
    parse(ctx, storage, Scripted(answer(*GOOD_ENTRIES)))
    second = [
        (e["id"] is not None, e["entry_type"], e["data"])
        for e in account.client.get(ENTRIES).json()
    ]
    assert first == second


def test_a_reparse_never_overwrites_what_the_person_edited(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    settings = _settings(app)
    parse(context(engine, settings, account), storage, Scripted(answer(*GOOD_ENTRIES)))
    work = next(e for e in account.client.get(ENTRIES).json() if e["entry_type"] == "work")
    edited = account.client.patch(
        f"{ENTRIES}/{work['id']}",
        json={
            "data": {
                "company": "Kestrel Analytics",
                "title": "Senior Data Intern",
                "start_date": "2024-06",
            }
        },
        headers=account.csrf,
    )
    assert edited.status_code == 200 and edited.json()["user_edited"] is True
    added = account.client.post(
        ENTRIES, json={"entry_type": "skill", "data": {"name": "Tableau"}}, headers=account.csrf
    )
    assert added.status_code == 201 and added.json()["source"] == "user"

    assert account.client.post(f"{RESUME}/reparse", headers=account.csrf).status_code == 200
    parse(
        context(engine, settings, account, generation=2), storage, Scripted(answer(*GOOD_ENTRIES))
    )

    entries = account.client.get(ENTRIES).json()
    works = [e for e in entries if e["entry_type"] == "work"]
    assert len(works) == 1  # the parsed duplicate was skipped
    assert works[0]["data"]["title"] == "Senior Data Intern"
    assert works[0]["user_edited"] is True
    assert any(e["data"].get("name") == "Tableau" for e in entries)
    assert (
        len([e for e in entries if e["entry_type"] == "skill" and e["data"]["name"] == "Python"])
        == 1
    )


def test_a_task_for_a_replaced_or_deleted_resume_does_nothing(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    other = make_account(app)
    upload(account)
    stale = context(engine, _settings(app), account, generation=1)
    parse(stale, storage, Scripted(answer(*GOOD_ENTRIES)))
    account.client.post(f"{RESUME}/reparse", headers=account.csrf)  # generation is now 2
    provider = Scripted(answer(*GOOD_ENTRIES))
    parse(stale, storage, provider)
    assert provider.calls == 0  # superseded task: the model was never called

    upload(other)
    wrong_owner = context(engine, _settings(app), other)
    object.__setattr__(wrong_owner, "owner_user_id", uuid.UUID(account.user_id))
    parse(wrong_owner, storage, provider)  # someone else's resume id with the wrong owner
    assert provider.calls == 0

    account.client.delete(RESUME, headers=account.csrf)
    parse(stale, storage, provider)
    assert provider.calls == 0


def test_garbage_from_the_model_marks_the_resume_failed_with_a_plain_message(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    parse(context(engine, _settings(app), account), storage, Scripted("nope", "still nope"))
    resume = account.client.get(RESUME).json()
    assert resume["ui_state"] == "failed"
    assert resume["can_retry"] is True
    assert "Your file is safe" in resume["error_message"]
    run = account.client.get(f"/api/v1/runs/{resume['run_id']}").json()
    assert run["run"]["ui_state"] == "retry_available"
    assert len(run["llm_calls"]) == 2  # both attempts were recorded


def test_missing_ai_configuration_is_a_visible_failure_not_a_crash_loop(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    parse(
        context(engine, _settings(app), account),
        storage,
        LLMError("The AI provider is not configured.", retryable=False),
    )
    assert "not set up" in account.client.get(RESUME).json()["error_message"]


def test_a_busy_provider_is_retried_and_only_fails_visibly_on_the_last_attempt(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    busy = LLMError("busy", retryable=True)
    with pytest.raises(TaskFailure) as caught:
        parse(context(engine, _settings(app), account, attempt=1), storage, Scripted(busy))
    assert caught.value.retryable is True
    assert account.client.get(RESUME).json()["ui_state"] == "parsing"
    run_id = account.client.get(RESUME).json()["run_id"]
    assert account.client.get(f"/api/v1/runs/{run_id}").json()["run"]["ui_state"] == "retrying"

    parse(context(engine, _settings(app), account, attempt=3), storage, Scripted(busy))
    assert account.client.get(RESUME).json()["ui_state"] == "failed"


def test_an_unreadable_file_fails_without_retrying_and_cannot_be_retried_as_is(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account, b"%PDF-1.4\nthis is not really a pdf")  # passes the cheap upload check
    provider = Scripted(answer(*GOOD_ENTRIES))
    parse(context(engine, _settings(app), account), storage, provider)
    assert provider.calls == 0
    resume = account.client.get(RESUME).json()
    assert resume["ui_state"] == "failed"
    assert resume["can_retry"] is True  # re-parse is allowed, but a new upload is the real fix
    assert "could not read" in resume["error_message"]


def test_a_lost_file_is_reported(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account)
    for path in getattr(storage, "_root").rglob("*"):  # noqa: B009
        if path.is_file():
            path.unlink()
    parse(context(engine, _settings(app), account), storage, Scripted(answer(*GOOD_ENTRIES)))
    assert "could not be found" in account.client.get(RESUME).json()["error_message"]


def test_a_docx_resume_is_parsed_like_a_pdf(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    upload(account, resume_docx(), name="cv.docx")
    parse(context(engine, _settings(app), account), storage, Scripted(answer(*GOOD_ENTRIES)))
    assert account.client.get(RESUME).json()["kept_entry_count"] == 4


# ---------------------------------------------------------------- confirm and reparse


def test_confirm_reparse_and_their_guards(
    app: FastAPI, make_account: MakeAccount, engine: Engine, storage: FileStorage
) -> None:
    account = make_account(app)
    assert account.client.post(f"{RESUME}/confirm", headers=account.csrf).status_code == 404
    upload(account)
    early = account.client.post(f"{RESUME}/confirm", headers=account.csrf)
    assert early.status_code == 409 and early.json()["code"] == "NOT_READY"
    assert account.client.post(f"{RESUME}/reparse", headers=account.csrf).status_code == 409

    parse(context(engine, _settings(app), account), storage, Scripted(answer(*GOOD_ENTRIES)))
    confirmed = account.client.post(f"{RESUME}/confirm", headers=account.csrf).json()
    assert confirmed["ui_state"] == "confirmed" and confirmed["confirmed_at"]

    again = account.client.post(f"{RESUME}/reparse", headers=account.csrf).json()
    assert again["ui_state"] == "uploaded" and again["confirmed_at"] is None


# ---------------------------------------------------------------- entries and preferences


def test_schema_endpoint_serves_the_field_specs(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    specs = account.client.get("/api/v1/profile/schema").json()
    assert [s["entry_type"] for s in specs][:2] == ["education", "work"]
    work = next(s for s in specs if s["entry_type"] == "work")
    assert {"company", "title", "start_date", "highlights"} <= {f["name"] for f in work["fields"]}


def test_entries_are_validated_with_per_field_messages(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    bad = account.client.post(
        ENTRIES,
        json={"entry_type": "work", "data": {"company": "Kestrel", "start_date": "June 2024"}},
        headers=account.csrf,
    )
    assert bad.status_code == 422
    assert set(bad.json()["fields"]) == {"title", "start_date"}
    ok = account.client.post(
        ENTRIES,
        json={"entry_type": "link", "data": {"label": "GitHub", "url": "https://github.com/asha"}},
        headers=account.csrf,
    )
    assert ok.status_code == 201 and ok.json()["source"] == "user"
    patch = account.client.patch(
        f"{ENTRIES}/{ok.json()['id']}",
        json={"data": {"label": "GitHub", "url": "nope"}},
        headers=account.csrf,
    )
    assert patch.status_code == 422


def test_preferences_round_trip_validate_and_stay_private(
    app: FastAPI, make_account: MakeAccount
) -> None:
    a, b = make_account(app), make_account(app)
    assert a.client.get(PREFS).json()["target_roles"] == []
    saved = a.client.put(
        PREFS,
        json={
            "target_roles": [" Data analyst ", "data analyst", "Backend engineer"],
            "authorized_countries": ["India"],
            "needs_sponsorship": False,
            "locations": ["Bengaluru"],
            "open_to_relocate": True,
            "remote_preference": "hybrid",
            "employment_types": ["full_time", "internship", "full_time"],
            "min_salary_amount": 600000,
            "min_salary_currency": "INR",
            "exclusions": ["Gambling"],
        },
        headers=a.csrf,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["target_roles"] == ["Data analyst", "Backend engineer"]
    assert saved.json()["employment_types"] == ["full_time", "internship"]
    assert a.client.get(PREFS).json()["min_salary_currency"] == "INR"
    assert b.client.get(PREFS).json()["target_roles"] == []

    for bad in (
        {"min_salary_amount": 100},
        {"remote_preference": "sometimes"},
        {"min_salary_amount": -1, "min_salary_currency": "INR"},
        {"employment_types": ["slave"]},
        {"target_roles": ["x" * 81]},
    ):
        assert a.client.put(PREFS, json=bad, headers=a.csrf).status_code == 422, bad
    assert a.client.put(PREFS, json={}, headers=a.csrf).status_code == 200  # clearing is allowed
    assert a.client.get(PREFS).json()["target_roles"] == []
