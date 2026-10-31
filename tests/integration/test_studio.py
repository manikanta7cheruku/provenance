"""Checkpoint 2.1: the resume studio API, versions, exports and the PDF task.

The PDF engine needs native libraries that are only in the Docker image, so these tests replace it
with a stand-in that returns a real, tiny PDF. The engine itself is tested on its own in
tests/pdf/test_resume_pdf.py, which runs inside the image.
"""

import io
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import Account
from pypdf import PdfWriter
from resume_helpers import ENTRIES_FOR_RENDER, bullets, para, text_node
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

import pv_worker.handlers.render_resume as render_module
from pv_config import Settings
from pv_files import FileStorage, RenderedPdf, RenderError, StorageError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.render_resume import run_render

STUDIO = "/api/v1/studio"
ENTRIES = "/api/v1/profile/entries"
MakeAccount = Callable[..., Account]


def tiny_pdf(pages: int = 1) -> RenderedPdf:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    return RenderedPdf(data=buffer.getvalue(), page_count=pages)


@pytest.fixture
def stub_pdf(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Replace the PDF engine. The list collects the HTML each call was given."""
    seen: list[str] = []

    def fake(html: str) -> RenderedPdf:
        seen.append(html)
        return tiny_pdf(2)

    monkeypatch.setattr(render_module, "html_to_pdf", fake)
    yield seen


def add_entries(account: Account) -> None:
    for entry_type, data in ENTRIES_FOR_RENDER:
        response = account.client.post(
            ENTRIES, json={"entry_type": entry_type, "data": data}, headers=account.csrf
        )
        assert response.status_code == 201, response.text


def create(account: Account, **body: Any) -> Any:
    return account.client.post(
        f"{STUDIO}/resumes",
        json={"start": "profile", "template": "classic", **body},
        headers=account.csrf,
    )


def make_doc(account: Account, **body: Any) -> dict[str, Any]:
    response = create(account, **body)
    assert response.status_code == 201, response.text
    return dict(response.json())


def save(account: Account, doc: dict[str, Any], content: dict[str, Any], **extra: Any) -> Any:
    return account.client.put(
        f"{STUDIO}/resumes/{doc['id']}",
        json={"content": content, "revision": doc["revision"], **extra},
        headers=account.csrf,
    )


def context(
    engine: Engine, settings: Settings, account: Account, export_id: str, *, attempt: int = 1,
    owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        run_id = db.execute(
            text("SELECT run_id FROM resume_exports WHERE id = :i"), {"i": export_id}
        ).scalar_one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="render_resume_pdf", args={"export_id": export_id},
        secret={}, attempt=attempt, max_attempts=3, owner_user_id=uuid.UUID(owner or account.user_id),
        run_id=run_id, settings=settings, engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def start_export(account: Account, doc: dict[str, Any]) -> dict[str, Any]:
    response = account.client.post(f"{STUDIO}/resumes/{doc['id']}/exports", headers=account.csrf)
    assert response.status_code == 202, response.text
    return dict(response.json())


# ------------------------------------------------------------------------------ options


def test_options_list_templates_with_their_ats_flag_and_the_plan_limit(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    body = account.client.get(f"{STUDIO}/options").json()
    assert [t["key"] for t in body["templates"]] == ["classic", "modern", "compact"]
    assert all(t["ats_safe"] is True for t in body["templates"])
    assert body["max_resumes"] == 1 and "a4" in body["papers"] and "letter" in body["papers"]


def test_the_studio_needs_a_session_and_the_csrf_token(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    assert TestClient(app).get(f"{STUDIO}/resumes").status_code == 401
    no_csrf = account.client.post(
        f"{STUDIO}/resumes", json={"start": "blank", "template": "classic"}
    )
    assert no_csrf.status_code in (401, 403)


# -------------------------------------------------------------------------------- creating


def test_a_first_draft_comes_from_the_profile_and_nothing_is_invented(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    add_entries(account)
    doc = make_doc(account)
    content = doc["content"]
    words = " ".join(
        str(v)
        for section in content["sections"]
        for block in section["blocks"]
        for v in (block["heading"], block["subheading"], block["dates"])
    )
    for expected in (
        "Data Intern",
        "Kestrel Analytics",
        "2025-06 to 2025-08",
        "B.E. Computer Science",
        "Churn model",
    ):
        assert expected in words
    assert doc["revision"] == 1 and doc["template"] == "classic" and doc["title"] == "My resume"


def test_a_blank_start_and_the_one_resume_limit(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    first = make_doc(account, start="blank", template="modern")
    assert first["content"]["sections"] == [] and first["template"] == "modern"
    second = create(account)
    assert second.status_code == 409 and second.json()["code"] == "RESUME_LIMIT"
    assert "one resume" in second.json()["message"]
    assert len(account.client.get(f"{STUDIO}/resumes").json()) == 1


def test_a_bad_template_is_refused(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert create(account, template="neon").status_code == 422


# ---------------------------------------------------------------------------------- saving


def test_saving_raises_the_revision_and_returns_a_clean_copy(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    content = doc["content"]
    content["header"]["name"] = "  Asha   Rao "
    content["evil"] = "<script>alert(1)</script>"
    saved = save(account, doc, content)
    assert saved.status_code == 200 and saved.json()["revision"] == 2
    stored = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    assert stored["header"]["name"] == "Asha   Rao"
    assert "evil" not in stored and "script" not in str(stored)


def test_a_save_from_an_old_revision_is_refused_and_changes_nothing(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    first = doc["content"]
    first["header"]["name"] = "From the first tab"
    assert save(account, doc, first).status_code == 200
    second = doc["content"]
    second["header"]["name"] = "From a stale tab"
    stale = save(account, doc, second)  # still says revision 1
    assert stale.status_code == 409 and stale.json()["code"] == "REVISION_CONFLICT"
    now = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()
    assert now["content"]["header"]["name"] == "From the first tab" and now["revision"] == 2


def test_bad_content_is_refused_next_to_the_field_and_nothing_is_stored(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    content = doc["content"]
    content["style"]["accent"] = "#ffee88"
    content["sections"] = [
        {"kind": "experience", "title": "Experience", "blocks": [
            {"heading": "Role", "body": {"type": "doc", "content": [{"type": "image", "attrs": {"src": "http://evil"}}]}}
        ]}
    ]  # fmt: skip
    refused = save(account, doc, content)
    assert refused.status_code == 422
    fields = refused.json()["fields"]
    assert "too light" in fields["style.accent"] and "sections.0.blocks.0.body.0" in fields
    assert account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["revision"] == 1


def test_restore_points_are_kept_at_most_every_couple_of_minutes_unless_asked(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    for n in range(3):  # three quick autosaves
        doc["content"]["header"]["name"] = f"Name {n}"
        doc["revision"] = save(account, doc, doc["content"]).json()["revision"]
    versions = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    assert [v["revision"] for v in versions] == [1]  # only the first, the rest were too soon
    doc["content"]["header"]["name"] = "Deliberate"
    save(account, doc, doc["content"], checkpoint=True)
    versions = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    assert [v["revision"] for v in versions] == [4, 1]


def test_only_the_latest_versions_are_kept(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    for n in range(25):
        doc["content"]["header"]["name"] = f"Name {n}"
        doc["revision"] = save(account, doc, doc["content"], checkpoint=True).json()["revision"]
    assert len(account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()) == 20


def test_restoring_an_earlier_version_keeps_the_present_one_and_needs_the_current_revision(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    doc["content"]["header"]["name"] = "Original"
    doc["revision"] = save(account, doc, doc["content"], checkpoint=True).json()["revision"]
    doc["content"]["header"]["name"] = "Changed"
    doc["revision"] = save(account, doc, doc["content"], checkpoint=True).json()["revision"]
    versions = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    original = next(
        v for v in versions if v["revision"] == 2
    )  # content as it was when "Original" was current
    url = f"{STUDIO}/resumes/{doc['id']}/versions/{original['id']}/restore"
    stale = account.client.post(url, json={"revision": 1}, headers=account.csrf)
    assert stale.status_code == 409
    restored = account.client.post(url, json={"revision": doc["revision"]}, headers=account.csrf)
    assert (
        restored.status_code == 200 and restored.json()["content"]["header"]["name"] == "Original"
    )
    assert restored.json()["revision"] == doc["revision"] + 1
    after = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    assert doc["revision"] in [v["revision"] for v in after]  # "Changed" can be restored too


# ------------------------------------------------------------------------------- previewing


def test_the_preview_is_the_server_html_for_unsaved_content_and_stores_nothing(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    content = doc["content"]
    content["header"]["name"] = "<script>alert(1)</script>"
    content["sections"] = [
        {"kind": "summary", "title": "Summary", "blocks": [{"body": bullets("Did <b>things</b>")}]}
    ]
    response = account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/preview", json={"content": content}, headers=account.csrf
    )
    html = response.json()["html"]
    assert response.status_code == 200
    assert (
        "<script" not in html and "&lt;script&gt;" in html and "&lt;b&gt;things&lt;/b&gt;" in html
    )
    assert (
        "/api/v1/studio/fonts/ibm-plex-sans-latin-400-normal.woff" in html and "box-shadow" in html
    )
    assert account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["revision"] == 1


def test_an_invalid_preview_is_explained_and_another_persons_resume_is_not_found(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    bad = doc["content"]
    bad["style"]["template"] = "neon"
    url = f"{STUDIO}/resumes/{doc['id']}/preview"
    assert account.client.post(url, json={"content": bad}, headers=account.csrf).status_code == 422
    stranger = make_account(app)
    ok = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    assert stranger.client.post(url, json={"content": ok}, headers=stranger.csrf).status_code == 404


# ------------------------------------------------------------------------------------ fonts


def test_fonts_are_public_cacheable_files_and_nothing_else_can_be_read(
    app: FastAPI, make_account: MakeAccount
) -> None:
    client = TestClient(app)
    response = client.get(f"{STUDIO}/fonts/ibm-plex-sans-latin-400-normal.woff")
    assert response.status_code == 200 and response.content[:4] == b"wOFF"
    assert response.headers["access-control-allow-origin"] == "*"
    assert "immutable" in response.headers["cache-control"]
    for name in ("..%2F..%2F.env", "LICENSE-newsreader.txt", "nope.woff", "%2e%2e%2fsecret"):
        assert client.get(f"{STUDIO}/fonts/{name}").status_code == 404


# ----------------------------------------------------------------------------------- exports


def test_an_export_is_made_by_the_worker_stored_privately_and_downloaded_by_its_owner(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    add_entries(account)
    doc = make_doc(account)
    doc["content"]["header"]["name"] = "Asha Rao"
    save(account, doc, doc["content"])
    export = start_export(account, doc)
    assert export["ui_state"] == "preparing"
    again = account.client.post(f"{STUDIO}/resumes/{doc['id']}/exports", headers=account.csrf)
    assert again.status_code == 409 and again.json()["code"] == "EXPORT_IN_PROGRESS"

    run_render(context(engine, settings, account, export["id"]), storage=storage)
    assert len(stub_pdf) == 1 and "Asha Rao" in stub_pdf[0] and "@page" in stub_pdf[0]
    listed = account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()
    assert (
        listed[0]["ui_state"] == "ready"
        and listed[0]["page_count"] == 2
        and listed[0]["revision"] == 2
    )

    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM resume_exports")).scalar_one()
    assert key.startswith("exports/") and "Asha" not in key and storage.get(key)[:4] == b"%PDF"

    got = account.client.get(f"{STUDIO}/exports/{export['id']}/download")
    assert got.status_code == 200 and got.content[:4] == b"%PDF"
    assert got.headers["content-type"] == "application/pdf"
    assert got.headers["content-disposition"] == 'attachment; filename="Asha Rao Resume.pdf"'
    assert (
        got.headers["x-content-type-options"] == "nosniff"
        and "no-store" in got.headers["cache-control"]
    )


def test_another_person_cannot_download_or_list_an_export(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    doc = make_doc(account, start="blank")
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    stranger = make_account(app)
    assert stranger.client.get(f"{STUDIO}/exports/{export['id']}/download").status_code == 404
    assert stranger.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").status_code == 404
    assert (
        stranger.client.post(
            f"{STUDIO}/resumes/{doc['id']}/exports", headers=stranger.csrf
        ).status_code
        == 404
    )


def test_the_file_name_never_carries_odd_characters(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    doc = make_doc(account, start="blank")
    doc["content"]["header"]["name"] = 'A/../"B"\r\nSet-Cookie: x'
    save(account, doc, doc["content"])
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    header = account.client.get(f"{STUDIO}/exports/{export['id']}/download").headers[
        "content-disposition"
    ]
    assert (
        "\n" not in header and "/" not in header.split("filename=")[1] and header.endswith('.pdf"')
    )


def test_a_pdf_that_cannot_be_made_is_a_visible_failure_and_a_new_try_is_allowed(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    def broken(html: str) -> RenderedPdf:
        raise RenderError("no")

    monkeypatch.setattr(render_module, "html_to_pdf", broken)
    account = make_account(app)
    doc = make_doc(account, start="blank")
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    item = account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()[0]
    assert item["ui_state"] == "failed" and "Your resume is safe" in item["error_message"]
    assert account.client.get(f"{STUDIO}/exports/{export['id']}/download").status_code == 404
    assert (
        account.client.post(
            f"{STUDIO}/resumes/{doc['id']}/exports", headers=account.csrf
        ).status_code
        == 202
    )


def test_a_storage_hiccup_is_retried_and_fails_visibly_on_the_last_attempt(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, stub_pdf: list[str]
) -> None:
    class Broken:
        def put(self, key: str, data: bytes) -> None:
            raise StorageError("disk")

        def get(self, key: str) -> bytes:
            raise StorageError("disk")

        def delete(self, key: str) -> None: ...

        def exists(self, key: str) -> bool:
            return False

    account = make_account(app)
    doc = make_doc(account, start="blank")
    export = start_export(account, doc)
    with pytest.raises(TaskFailure) as raised:
        run_render(context(engine, settings, account, export["id"], attempt=1), storage=Broken())
    assert raised.value.retryable is True
    run_render(context(engine, settings, account, export["id"], attempt=3), storage=Broken())
    assert (
        account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()[0]["ui_state"]
        == "failed"
    )


def test_a_stale_foreign_or_finished_export_task_does_nothing(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    other = make_account(app)
    doc = make_doc(account, start="blank")
    export = start_export(account, doc)
    run_render(
        context(engine, settings, account, export["id"], owner=other.user_id), storage=storage
    )
    assert stub_pdf == []
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    assert len(stub_pdf) == 1


def test_only_the_newest_exports_are_kept(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    doc = make_doc(account, start="blank")
    keys: list[str] = []
    for _ in range(7):
        export = start_export(account, doc)
        run_render(context(engine, settings, account, export["id"]), storage=storage)
        with tenant_session(engine, uuid.UUID(account.user_id)) as db:
            keys.append(
                db.execute(
                    text("SELECT storage_key FROM resume_exports WHERE id = :i"),
                    {"i": export["id"]},
                ).scalar_one()
            )
    assert (
        len(account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json())
        == settings.studio_max_exports
    )
    assert not storage.exists(keys[0]) and storage.exists(keys[-1])


# ---------------------------------------------------------------------------------- deleting


def test_deleting_a_resume_removes_its_versions_exports_and_files_but_not_the_profile(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings, storage: FileStorage,
    stub_pdf: list[str],
) -> None:  # fmt: skip
    account = make_account(app)
    add_entries(account)
    doc = make_doc(account)
    save(account, doc, doc["content"], checkpoint=True)
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM resume_exports")).scalar_one()
    assert (
        account.client.delete(f"{STUDIO}/resumes/{doc['id']}", headers=account.csrf).status_code
        == 204
    )
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        for table in ("resume_documents", "resume_document_versions", "resume_exports"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608
    assert not storage.exists(key)
    assert len(account.client.get(ENTRIES).json()) == len(ENTRIES_FOR_RENDER)
    assert account.client.get(f"{STUDIO}/resumes/{doc['id']}").status_code == 404
    assert create(account).status_code == 201  # the free slot is free again


def test_deleting_cancels_a_waiting_export(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    start_export(account, doc)
    account.client.delete(f"{STUDIO}/resumes/{doc['id']}", headers=account.csrf)
    with Session(engine) as db:
        waiting = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'render_resume_pdf' "
                "AND state = 'queued' AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert waiting == 0


# ----------------------------------------------------------------------- isolation and audit


def test_tables_have_forced_row_level_security_and_hide_rows_from_other_tenants(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    other = make_account(app)
    doc = make_doc(account, start="blank")
    tables = ("resume_documents", "resume_document_versions", "resume_exports")
    with Session(engine) as db:
        flags = dict(
            db.execute(
                text(
                    "SELECT relname, relrowsecurity AND relforcerowsecurity FROM pg_class "
                    "WHERE relname = ANY(:t)"
                ),
                {"t": list(tables)},
            ).all()
        )
    assert flags == {t: True for t in tables}
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM resume_documents")).scalar_one() == 0
    with pytest.raises(DBAPIError), tenant_session(engine, uuid.UUID(other.user_id)) as db:
        db.execute(
            text("INSERT INTO resume_documents (owner_user_id, content) VALUES (:o, '{}'::jsonb)"),
            {"o": account.user_id},
        )
    stranger_paths = [
        ("get", f"{STUDIO}/resumes/{doc['id']}"),
        ("get", f"{STUDIO}/resumes/{doc['id']}/versions"),
    ]
    for method, url in stranger_paths:
        assert getattr(other.client, method)(url).status_code == 404
    assert (
        other.client.put(
            f"{STUDIO}/resumes/{doc['id']}",
            json={"content": doc["content"], "revision": 1},
            headers=other.csrf,
        ).status_code
        == 404
    )
    assert (
        other.client.delete(f"{STUDIO}/resumes/{doc['id']}", headers=other.csrf).status_code == 404
    )


def test_actions_are_audited_without_resume_text(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    add_entries(account)
    doc = make_doc(account)
    start_export(account, doc)
    account.client.delete(f"{STUDIO}/resumes/{doc['id']}", headers=account.csrf)
    with Session(engine) as db:
        rows = db.execute(
            text(
                "SELECT action, metadata::text FROM audit_events WHERE actor_user_id = :u AND action LIKE 'resume_doc.%' ORDER BY created_at"
            ),
            {"u": account.user_id},
        ).all()
    assert [r.action for r in rows] == [
        "resume_doc.created",
        "resume_doc.export_started",
        "resume_doc.deleted",
    ]
    assert not any("Kestrel" in (r[1] or "") or "Data Intern" in (r[1] or "") for r in rows)


def test_studio_limits_are_defined() -> None:
    from pv_domain.ratelimit import DEFAULT_POLICIES

    assert DEFAULT_POLICIES["studio_export_user"].limit == 10
    assert DEFAULT_POLICIES["studio_save_user"].limit == 600
    assert DEFAULT_POLICIES["studio_preview_user"].limit == 600


def test_rich_text_round_trips_through_a_save(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    doc = make_doc(account, start="blank")
    body = {
        "type": "doc",
        "content": [
            para(text_node("Hello", "bold", "highlight")),
            bullets("one", "two")["content"][0],
        ],
    }
    doc["content"]["sections"] = [
        {"kind": "summary", "title": "Summary", "blocks": [{"heading": "", "body": body}]}
    ]
    assert save(account, doc, doc["content"]).status_code == 200
    stored = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    first = stored["sections"][0]["blocks"][0]["body"]["content"]
    assert first[0]["content"][0]["marks"] == [{"type": "bold"}, {"type": "highlight"}]
    assert first[1]["type"] == "bulletList" and len(first[1]["content"]) == 2
