"""Checkpoint 2.2: the free canvas through the studio API, versions, preview and the export task."""

from collections.abc import Iterator
from typing import Any

import pytest
from canvas_helpers import canvas, rich, sample_canvas, shape_el, text_el
from fastapi import FastAPI
from helpers import Account
from sqlalchemy.engine import Engine
from test_studio import context, make_doc, save, start_export, tiny_pdf  # noqa: F401

import pv_worker.handlers.render_resume as render_module
from pv_config import Settings
from pv_files import FileStorage, RenderedPdf
from pv_worker.handlers.render_resume import run_render

STUDIO = "/api/v1/studio"


@pytest.fixture
def stub_pdf(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    seen: list[str] = []

    def fake(html: str) -> RenderedPdf:
        seen.append(html)
        return tiny_pdf(1)

    monkeypatch.setattr(render_module, "html_to_pdf", fake)
    yield seen


def test_a_canvas_document_is_saved_read_back_and_summarised(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    content = sample_canvas()
    saved = save(account, doc, content)
    assert saved.status_code == 200 and saved.json()["revision"] == 2
    got = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()
    assert got["content"]["version"] == 2
    assert [e["id"] for e in got["content"]["pages"][0]["elements"]][:2] == ["name", "headline"]
    assert got["template"] == "free"


def test_a_bad_canvas_is_refused_next_to_the_field_and_nothing_is_stored(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    bad = canvas(
        text_el("a", 180, 10, 50, 8, rich("x")),
        text_el("b", 10, 10, 50, 8, rich("y"), size=2),
        shape_el("c", 10, 290, 50, 20, fill="url(javascript:1)"),
    )
    refused = save(account, doc, bad)
    assert refused.status_code == 422
    fields = refused.json()["fields"]
    assert "right edge" in fields["pages.0.elements.0.w"]
    assert (
        fields["pages.0.elements.1.size"]
        and fields["pages.0.elements.2.fill"]
        and fields["pages.0.elements.2.h"]
    )
    assert account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["revision"] == 1


def test_unknown_element_kinds_images_and_markup_cannot_be_saved(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    raw = canvas(text_el("a", 10, 10, 50, 8, rich("x")))
    raw["pages"][0]["elements"].append(
        {"kind": "image", "x": 1, "y": 1, "w": 5, "h": 5, "src": "http://evil.example/a.png"}
    )
    assert save(account, doc, raw).status_code == 422
    html = canvas(
        text_el(
            "a",
            10,
            10,
            50,
            8,
            {"type": "doc", "content": [{"type": "html", "content": "<script>1</script>"}]},
        )
    )
    assert save(account, doc, html).status_code == 422


def test_a_text_box_taller_than_the_page_is_trimmed_not_refused(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    saved = save(account, doc, canvas(text_el("a", 10, 280, 50, 40, rich("a long text"))))
    assert saved.status_code == 200
    stored = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]["pages"][0][
        "elements"
    ][0]
    assert stored["h"] == 17.0


def test_the_server_preview_of_a_canvas_is_the_pages_as_html(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    response = account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/preview",
        json={"content": sample_canvas()},
        headers=account.csrf,
    )
    html = response.json()["html"]
    assert response.status_code == 200 and html.count('<section class="page">') == 1
    assert "Asha Rao" in html and "box-shadow" in html and "<script" not in html


def test_moving_to_the_canvas_keeps_the_guided_version_as_an_earlier_version(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    doc["content"]["header"]["name"] = "Guided Name"
    doc["revision"] = save(account, doc, doc["content"]).json()["revision"]
    guided_revision = doc["revision"]
    converted = account.client.put(
        f"{STUDIO}/resumes/{doc['id']}",
        json={"content": sample_canvas(), "revision": guided_revision, "checkpoint": True},
        headers=account.csrf,
    )
    assert converted.status_code == 200
    versions = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    guided = next(v for v in versions if v["revision"] == guided_revision)
    restored = account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/versions/{guided['id']}/restore",
        json={"revision": converted.json()["revision"]},
        headers=account.csrf,
    )
    assert restored.status_code == 200
    body = restored.json()["content"]
    assert body["version"] == 1 and body["header"]["name"] == "Guided Name"


def test_the_pdf_task_draws_a_canvas_document_as_pages(
    app: FastAPI,
    make_account: Any,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
    stub_pdf: list[str],
) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    two_pages = sample_canvas()
    two_pages["pages"].append(
        {"id": "p2", "elements": [text_el("n", 16, 16, 100, 8, rich("Second page text"))]}
    )
    assert save(account, doc, two_pages).status_code == 200
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    html = stub_pdf[0]
    assert html.count('<section class="page">') == 2 and "Second page text" in html
    assert "@page{size:210mm 297mm;margin:0}" in html and "box-shadow" not in html
    listed = account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()
    assert listed[0]["ui_state"] == "ready"


def test_a_canvas_saved_by_one_person_is_not_visible_to_another(
    app: FastAPI, make_account: Any
) -> None:
    account: Account = make_account(app)
    stranger: Account = make_account(app)
    doc = make_doc(account, start="blank")
    save(account, doc, sample_canvas())
    assert stranger.client.get(f"{STUDIO}/resumes/{doc['id']}").status_code == 404
    assert (
        stranger.client.post(
            f"{STUDIO}/resumes/{doc['id']}/preview",
            json={"content": sample_canvas()},
            headers=stranger.csrf,
        ).status_code
        == 404
    )


def test_a_save_larger_than_the_limit_is_refused(app: FastAPI, make_account: Any) -> None:
    account: Account = make_account(app)
    doc = make_doc(account, start="blank")
    many = canvas(*[text_el(f"e{i}", 10, 10, 20, 5, rich("x")) for i in range(151)])
    refused = save(account, doc, many)
    assert refused.status_code == 422 and "at most" in refused.json()["fields"]["pages"]
