"""Checkpoint 2.11: pictures for the resume studio. Upload and refusal, private storage and serving,
whose picture a resume may use, and the PDF."""

import hashlib
import io
import uuid
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import quote

import pytest
from canvas_helpers import IMAGE_ID, canvas, icon_el, image_el, rich, text_el
from fastapi import FastAPI
from helpers import Account
from PIL import Image
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_studio import context, make_doc, save, start_export, tiny_pdf

import pv_api.services.image_service as image_service
import pv_worker.handlers.render_resume as render_module
from pv_config import Settings
from pv_files import FileStorage, RenderedPdf
from pv_persistence.tenancy import tenant_session
from pv_worker.handlers.render_resume import run_render

IMAGES = "/api/v1/studio/images"
STUDIO = "/api/v1/studio"
MakeAccount = Callable[..., Account]


def photo(
    seed: int = 0, size: tuple[int, int] = (320, 240), fmt: str = "JPEG", **save_args: Any
) -> bytes:
    image = Image.effect_mandelbrot(size, (-2 + seed * 0.01, -1.5, 1, 1.5), 40 + seed).convert(
        "RGB"
    )
    out = io.BytesIO()
    image.save(out, format=fmt, **save_args)
    return out.getvalue()


def upload(account: Account, data: bytes, name: str = "me.jpg") -> Any:
    return account.client.post(
        IMAGES,
        content=data,
        headers={
            **account.csrf,
            "X-Filename": quote(name),
            "Content-Type": "application/octet-stream",
        },
    )


def add(account: Account, seed: int = 0, **kw: Any) -> dict[str, Any]:
    response = upload(account, photo(seed, **kw))
    assert response.status_code == 201, response.text
    return dict(response.json())


def listing(account: Account) -> Any:
    response = account.client.get(IMAGES)
    assert response.status_code == 200, response.text
    return response.json()


def doc_with(account: Account, *elements: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    doc = make_doc(account, start="blank")
    return doc, save(account, doc, canvas(*elements))


@pytest.fixture
def stub_pdf(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    seen: list[str] = []

    def fake(html: str) -> RenderedPdf:
        seen.append(html)
        return tiny_pdf(1)

    monkeypatch.setattr(render_module, "html_to_pdf", fake)
    yield seen


# --------------------------------------------------------------------- the schema


def test_the_table_has_forced_security_and_sane_checks(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = db.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'resume_images'"
            )
        ).one()
    assert tuple(flags) == (True, True)
    base = "INSERT INTO resume_images (owner_user_id, storage_key, mime, width, height, size_bytes, sha256) VALUES (:u, 'images/a', {mime}, {w}, {h}, {s}, {hash})"
    good = {"mime": "'image/jpeg'", "w": "10", "h": "10", "s": "10", "hash": "repeat('a', 64)"}
    bad = {
        "a mime type that is not stored": {**good, "mime": "'image/svg+xml'"},
        "a width of zero": {**good, "w": "0"},
        "a picture wider than the stored limit": {**good, "w": "4001"},
        "a size of zero": {**good, "s": "0"},
        "a short hash": {**good, "hash": "'abc'"},
    }
    for name, values in bad.items():
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(base.format(**values)), {"u": str(uid)})
        assert name
    with tenant_session(engine, uid) as db:
        db.execute(text(base.format(**good)), {"u": str(uid)})
    with (
        pytest.raises(DBAPIError),
        tenant_session(engine, uid) as db,
    ):  # one row per person and picture
        db.execute(text(base.format(**good)), {"u": str(uid)})


# --------------------------------------------------------------------- uploading


def test_a_picture_is_stored_as_a_new_file_that_is_not_the_upload(
    app: FastAPI, make_account: MakeAccount, storage: FileStorage, engine: Engine
) -> None:
    account = make_account(app)
    original = photo(3, (800, 600))
    image = add(account, 3, size=(800, 600))
    assert (image["width"], image["height"], image["mime"]) == (800, 600, "image/jpeg")
    assert image["url"] == f"{IMAGES}/{image['id']}/file" and image["used"] is False
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key, digest = db.execute(text("SELECT storage_key, sha256 FROM resume_images")).one()
    stored = storage.get(key)
    assert stored != original and hashlib.sha256(stored).hexdigest() == digest
    assert key.startswith("images/") and key != "images/" + image["id"]


def test_the_kind_comes_from_the_bytes_not_the_name(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    response = upload(account, photo(1, fmt="PNG"), name="holiday.pdf")
    assert response.status_code == 201 and response.json()["original_name"] == "holiday.pdf"


def test_a_hostile_file_name_is_made_safe(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    response = upload(account, photo(2), name='../../etc/pass"wd;<script>.jpg')
    assert response.status_code == 201
    name = response.json()["original_name"]
    assert "/" not in name and '"' not in name and ";" not in name and len(name) <= 120


def test_camera_place_and_time_never_reach_the_stored_file(
    app: FastAPI, make_account: MakeAccount, storage: FileStorage, engine: Engine
) -> None:
    account = make_account(app)
    exif = Image.Exif()
    exif[0x010F] = "Acme Camera"
    exif[0x8825] = {1: "N", 2: (18.0, 31.0, 0.0), 3: "E", 4: (73.0, 51.0, 0.0)}
    data = photo(4, exif=exif) + b"<script>hidden payload</script>"
    assert b"Acme Camera" in data
    add_response = upload(account, data)
    assert add_response.status_code == 201
    served = account.client.get(add_response.json()["url"]).content
    assert (
        b"Acme Camera" not in served
        and b"hidden payload" not in served
        and b"<script>" not in served
    )


def test_the_same_picture_twice_is_one_picture(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    first, second = add(account, 5), add(account, 5)
    assert first["id"] == second["id"] and listing(account)["count"] == 1


@pytest.mark.parametrize(
    ("data", "status", "words"),
    [
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            422,
            "not accepted",
        ),
        (b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", 422, "not accepted"),
        (b"%PDF-1.7 not a picture", 422, "not a picture"),
        (b"<html><script>alert(1)</script></html>", 422, "not a picture"),
        (b"", 422, "not a picture"),
        (b"\xff\xd8\xff" + b"\x00" * 300, 422, "damaged"),
        (b"\xff\xd8\xff" + b"\x00" * (6 * 1024 * 1024), 413, "too large"),
    ],
    ids=["svg", "gif", "pdf", "html", "empty", "damaged", "too-big"],
)
def test_pictures_that_cannot_be_used_are_refused_in_words_and_nothing_is_kept(
    app: FastAPI,
    make_account: MakeAccount,
    storage: FileStorage,
    data: bytes,
    status: int,
    words: str,
) -> None:
    account = make_account(app)
    response = upload(account, data)
    assert response.status_code == status, response.text
    assert words in response.json()["message"].lower() or words in response.json()["message"]
    assert listing(account)["count"] == 0


def test_a_picture_that_is_much_too_large_or_too_small_or_animated_says_so(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    huge = io.BytesIO()
    Image.new("1", (20_000, 20_000)).save(huge, format="PNG")
    assert "megapixels" in upload(account, huge.getvalue()).json()["message"]
    assert "too small" in upload(account, photo(0, (10, 10))).json()["message"]
    frames = [Image.new("RGB", (64, 64), (i * 40, 0, 0)) for i in range(3)]
    moving = io.BytesIO()
    frames[0].save(moving, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    assert "Animated" in upload(account, moving.getvalue()).json()["message"]
    assert listing(account)["count"] == 0


def test_the_number_of_pictures_and_the_space_they_take_are_limited(
    app: FastAPI, make_account: MakeAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = make_account(app)
    monkeypatch.setattr(image_service, "MAX_IMAGES_PER_USER", 2)
    add(account, 10)
    add(account, 11)
    over = upload(account, photo(12))
    assert over.status_code == 409 and "You can keep up to" in over.json()["message"]
    monkeypatch.setattr(image_service, "MAX_IMAGES_PER_USER", 20)
    monkeypatch.setattr(image_service, "MAX_USER_BYTES", 1)
    full = upload(account, photo(13))
    assert full.status_code == 409 and "space allowed" in full.json()["message"]
    assert listing(account)["count"] == 2


def test_uploading_needs_a_signed_in_writer(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert account.client.post(IMAGES, content=photo()).status_code in (401, 403)  # no CSRF token
    account.client.cookies.clear()
    assert upload(account, photo()).status_code == 401
    assert account.client.get(IMAGES).status_code == 401


# --------------------------------------------------------------------- serving


def test_only_the_owner_can_read_a_picture_and_it_is_served_with_a_type_we_chose(
    app: FastAPI, make_account: MakeAccount
) -> None:
    owner, other = make_account(app), make_account(app)
    image = add(owner, 20)
    served = owner.client.get(image["url"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in served.headers["content-security-policy"]
    assert served.headers["cache-control"].startswith("private")
    assert Image.open(io.BytesIO(served.content)).format == "JPEG"
    assert other.client.get(image["url"]).status_code == 404
    assert other.client.get(f"{IMAGES}/{uuid.uuid4()}/file").status_code == 404
    assert other.client.get(f"{IMAGES}/not-an-id/file").status_code == 422
    assert listing(other)["images"] == []
    owner.client.cookies.clear()
    assert owner.client.get(image["url"]).status_code == 401


def test_pictures_belong_to_their_owner_under_row_level_security(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    owner, other = make_account(app), make_account(app)
    add(owner, 21)
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM resume_images")).scalar_one() == 0


def test_the_list_says_what_is_accepted_and_how_much_room_is_left(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    add(account, 22)
    body = listing(account)
    assert body["accepted"] == ["JPEG", "PNG", "WebP"] and body["max_images"] == 20
    assert 0 < body["used_bytes"] < body["max_bytes"] and body["count"] == 1


# --------------------------------------------------------------------- in a resume


def test_a_resume_can_use_the_persons_own_picture_and_marks_it_used(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    image = add(account, 30)
    doc, saved = doc_with(
        account,
        text_el("a", 16, 16, 100, 8, rich("Asha")),
        image_el("p", 150, 12, 40, 50, image_id=image["id"]),
        icon_el("c", 16, 30, 4, 4),
    )
    assert saved.status_code == 200, saved.text
    got = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]["pages"][0][
        "elements"
    ]
    assert [e["kind"] for e in got] == ["text", "image", "icon"] and got[1]["image_id"] == image[
        "id"
    ]
    assert listing(account)["images"][0]["used"] is True


def test_another_persons_picture_and_a_made_up_one_are_refused_in_the_same_words(
    app: FastAPI, make_account: MakeAccount
) -> None:
    owner, other = make_account(app), make_account(app)
    theirs = add(owner, 31)
    doc = make_doc(other, start="blank")
    stranger = save(other, doc, canvas(image_el("p", 10, 10, 30, 30, image_id=theirs["id"])))
    made_up = save(other, doc, canvas(image_el("p", 10, 10, 30, 30, image_id=IMAGE_ID)))
    assert stranger.status_code == made_up.status_code == 422
    assert stranger.json()["fields"] == made_up.json()["fields"]
    assert "not available" in stranger.json()["fields"]["pages.0.elements.0.image_id"]
    assert other.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["revision"] == 1


def test_the_preview_draws_the_picture_from_its_own_bytes(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    image = add(account, 32)
    doc, _ = doc_with(
        account, image_el("p", 150, 12, 40, 50, image_id=image["id"], alt="Asha at work")
    )
    html = account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/preview",
        json={
            "content": canvas(
                image_el("p", 150, 12, 40, 50, image_id=image["id"], alt="Asha at work")
            )
        },
        headers=account.csrf,
    ).json()["html"]
    assert 'src="data:image/jpeg;base64,' in html and 'alt="Asha at work"' in html


def test_a_preview_of_another_persons_picture_is_refused(
    app: FastAPI, make_account: MakeAccount
) -> None:
    owner, other = make_account(app), make_account(app)
    theirs = add(owner, 33)
    doc = make_doc(other, start="blank")
    refused = other.client.post(
        f"{STUDIO}/resumes/{doc['id']}/preview",
        json={"content": canvas(image_el("p", 10, 10, 30, 30, image_id=theirs["id"]))},
        headers=other.csrf,
    )
    assert refused.status_code == 422


def test_the_pdf_task_draws_the_picture(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
    stub_pdf: list[str],
) -> None:
    account = make_account(app)
    image = add(account, 34)
    doc, saved = doc_with(
        account,
        text_el("a", 16, 16, 100, 8, rich("Asha")),
        image_el("p", 150, 12, 40, 50, image_id=image["id"]),
    )
    assert saved.status_code == 200
    export = start_export(account, doc)
    run_render(context(engine, settings, account, export["id"]), storage=storage)
    assert 'src="data:image/jpeg;base64,' in stub_pdf[0]
    assert (
        account.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()[0]["ui_state"] == "ready"
    )


def test_the_pdf_task_never_draws_a_picture_that_is_not_the_owners(
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    storage: FileStorage,
    stub_pdf: list[str],
) -> None:
    owner, other = make_account(app), make_account(app)
    theirs = add(owner, 35)
    doc = make_doc(other, start="blank")
    content = canvas(
        text_el("a", 16, 16, 100, 8, rich("Asha")),
        image_el("p", 10, 40, 30, 30, image_id=theirs["id"]),
    )
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:  # as if the check had been skipped
        db.execute(
            text("UPDATE resume_documents SET content = CAST(:c AS jsonb) WHERE id = :i"),
            {"c": __import__("json").dumps(content), "i": doc["id"]},
        )
    export = start_export(other, doc)
    run_render(context(engine, settings, other, export["id"]), storage=storage)
    assert stub_pdf == []
    assert (
        other.client.get(f"{STUDIO}/resumes/{doc['id']}/exports").json()[0]["ui_state"] == "failed"
    )


# --------------------------------------------------------------------- deleting


def test_an_unused_picture_is_deleted_with_its_file(
    app: FastAPI, make_account: MakeAccount, storage: FileStorage, engine: Engine
) -> None:
    account = make_account(app)
    image = add(account, 40)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        key = db.execute(text("SELECT storage_key FROM resume_images")).scalar_one()
    assert storage.exists(key)
    assert account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf).status_code == 204
    assert not storage.exists(key) and listing(account)["count"] == 0
    assert account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf).status_code == 404


def test_a_picture_in_use_cannot_be_deleted_and_the_message_says_why(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    image = add(account, 41)
    doc, _ = doc_with(account, image_el("p", 10, 10, 30, 30, image_id=image["id"]))
    refused = account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf)
    assert refused.status_code == 409 and "used in one of your resumes" in refused.json()["message"]
    assert listing(account)["count"] == 1
    # Taking it off the page is not enough while a saved version still has it.
    doc["revision"] = 2
    assert (
        save(
            account, doc, canvas(text_el("a", 16, 16, 100, 8, rich("Asha"))), checkpoint=True
        ).status_code
        == 200
    )
    assert account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf).status_code == 409
    # Deleting the resume deletes its versions, and then the picture can go.
    assert (
        account.client.delete(f"{STUDIO}/resumes/{doc['id']}", headers=account.csrf).status_code
        == 204
    )
    assert account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf).status_code == 204


def test_nobody_else_can_delete_a_picture(app: FastAPI, make_account: MakeAccount) -> None:
    owner, other = make_account(app), make_account(app)
    image = add(owner, 42)
    assert other.client.delete(f"{IMAGES}/{image['id']}", headers=other.csrf).status_code == 404
    assert listing(owner)["count"] == 1


def test_uploads_and_deletes_are_audited_without_the_picture(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    image = add(account, 43)
    account.client.delete(f"{IMAGES}/{image['id']}", headers=account.csrf)
    with Session(engine) as db:
        rows = list(
            db.execute(
                text(
                    "SELECT action, metadata FROM audit_events WHERE actor_user_id = :u AND action LIKE 'resume_image.%' ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        )
    assert [r.action for r in rows] == ["resume_image.uploaded", "resume_image.deleted"]
    assert rows[0].metadata["kind"] == "jpeg" and "bytes" in rows[0].metadata
    assert "me.jpg" not in str(rows[0].metadata)


def test_deleting_the_person_removes_their_pictures(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    add(account, 44)
    with Session(engine) as db, db.begin():
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": account.user_id})
        assert (
            db.execute(
                text("SELECT count(*) FROM resume_images WHERE owner_user_id = :u"),
                {"u": account.user_id},
            ).scalar_one()
            == 0
        )
