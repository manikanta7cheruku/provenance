"""Checkpoint 2.13: saved themes for the resume studio. Create, list, replace and delete, names, the
limit, readable colors, and whose theme it is."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_domain.resume_doc import FONT_PAIRS
from pv_domain.resume_themes import MAX_THEMES_PER_USER
from pv_persistence.tenancy import tenant_session

THEMES = "/api/v1/studio/themes"
MakeAccount = Callable[..., Account]


def theme(name: str = "Interview blue", **changes: Any) -> dict[str, Any]:
    return {
        "name": name,
        "font_pair": FONT_PAIRS[0],
        "accent": "#1f3d7a",
        "ink": "#1b1b1b",
        "muted": "#4a4a4a",
        "tint": "#eef1f6",
        **changes,
    }


def create(account: Account, body: dict[str, Any]) -> Any:
    return account.client.post(THEMES, json=body, headers=account.csrf)


def made(account: Account, name: str = "Interview blue", **changes: Any) -> dict[str, Any]:
    response = create(account, theme(name, **changes))
    assert response.status_code == 201, response.text
    return dict(response.json())


def listing(account: Account) -> Any:
    response = account.client.get(THEMES)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------- the schema


def test_the_table_has_forced_security_and_sane_checks(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = db.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = 'resume_themes'"
            )
        ).one()
    assert tuple(flags) == (True, True)
    base = (
        "INSERT INTO resume_themes (owner_user_id, name, font_pair, accent, ink, muted, tint) "
        "VALUES (:u, {name}, 'x', {accent}, '#111111', '#444444', '#eeeeee')"
    )
    for name, accent in (("''", "'#111111'"), ("'ok'", "'red'"), ("'ok'", "'#ABCDEF'")):
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(base.format(name=name, accent=accent)), {"u": str(uid)})
    with tenant_session(engine, uid) as db:
        db.execute(text(base.format(name="'Blue'", accent="'#111111'")), {"u": str(uid)})
    with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:  # a name, ignoring case
        db.execute(text(base.format(name="'BLUE'", accent="'#111111'")), {"u": str(uid)})


# --------------------------------------------------------------------- the routes


def test_a_theme_can_be_created_and_listed(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    assert listing(account) == {"themes": [], "count": 0, "max_themes": MAX_THEMES_PER_USER}
    one = made(account)
    assert one["name"] == "Interview blue" and one["accent"] == "#1f3d7a"
    made(account, "academic", accent="#7a1f3d", tint="#f5ebee")
    found = listing(account)
    assert found["count"] == 2
    assert [t["name"] for t in found["themes"]] == ["academic", "Interview blue"]


def test_a_theme_can_be_replaced_renamed_and_deleted(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    one = made(account)
    changed = account.client.put(
        f"{THEMES}/{one['id']}",
        json=theme("Final", accent="#0b5cad", tint="#e8f1fa"),
        headers=account.csrf,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["name"] == "Final" and changed.json()["accent"] == "#0b5cad"
    assert listing(account)["themes"][0]["name"] == "Final"
    gone = account.client.delete(f"{THEMES}/{one['id']}", headers=account.csrf)
    assert gone.status_code == 204
    assert listing(account)["count"] == 0
    again = account.client.delete(f"{THEMES}/{one['id']}", headers=account.csrf)
    assert again.status_code == 404


def test_a_theme_can_be_saved_again_under_its_own_name(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    one = made(account)
    same = account.client.put(
        f"{THEMES}/{one['id']}", json=theme(accent="#0b5cad"), headers=account.csrf
    )
    assert same.status_code == 200 and same.json()["accent"] == "#0b5cad"


def test_a_name_is_unique_for_a_person_ignoring_case(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    made(account, "Blue")
    clash = create(account, theme("blue"))
    assert clash.status_code == 409
    assert clash.json()["code"] == "THEME_NAME_TAKEN"
    assert "already have a theme" in clash.json()["fields"]["name"]
    other = made(account, "Green", accent="#1f5d3a", tint="#eaf2ec")
    rename = account.client.put(f"{THEMES}/{other['id']}", json=theme("BLUE"), headers=account.csrf)
    assert rename.status_code == 409 and rename.json()["code"] == "THEME_NAME_TAKEN"
    assert listing(account)["count"] == 2


def test_two_people_may_use_the_same_name(app: FastAPI, make_account: MakeAccount) -> None:
    first, second = make_account(app), make_account(app)
    made(first, "Blue")
    made(second, "Blue")


def test_bad_themes_are_refused_with_a_message_per_field(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    cases = {
        "name": theme(""),
        "font_pair": theme(font_pair="comic-sans"),
        "accent": theme(accent="red"),
        "ink": theme(ink="#dddddd"),
        "tint": theme(tint="#202020"),
    }
    for field, body in cases.items():
        response = create(account, body)
        assert response.status_code == 422, (field, response.text)
        assert field in response.json()["fields"]
    assert listing(account)["count"] == 0


def test_unknown_fields_are_refused(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    response = create(account, {**theme(), "margin_mm": 40})
    assert response.status_code == 422


def test_there_is_a_limit_per_person(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    for n in range(MAX_THEMES_PER_USER):
        made(account, f"Theme {n}")
    full = create(account, theme("One too many"))
    assert full.status_code == 409 and full.json()["code"] == "THEME_LIMIT"
    other = make_account(app)
    made(other, "Theme 0")


# --------------------------------------------------------------------- whose theme


def test_themes_belong_to_their_owner(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    mine, theirs = make_account(app), make_account(app)
    one = made(mine, "Mine")
    assert listing(theirs)["themes"] == []
    for call in (
        lambda: theirs.client.put(
            f"{THEMES}/{one['id']}", json=theme("Taken"), headers=theirs.csrf
        ),
        lambda: theirs.client.delete(f"{THEMES}/{one['id']}", headers=theirs.csrf),
    ):
        assert call().status_code == 404
    assert listing(mine)["themes"][0]["name"] == "Mine"
    # Even a query with the wrong person set sees nothing, because of Row Level Security.
    with tenant_session(engine, uuid.UUID(theirs.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM resume_themes")).scalar_one() == 0


def test_a_theme_needs_a_signed_in_person_and_a_csrf_token(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    assert account.client.post(THEMES, json=theme()).status_code in {400, 401, 403}
    account.client.cookies.clear()
    assert account.client.get(THEMES).status_code == 401


def test_themes_go_with_the_person_and_are_audited(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    one = made(account)
    account.client.put(f"{THEMES}/{one['id']}", json=theme("Two"), headers=account.csrf)
    account.client.delete(f"{THEMES}/{one['id']}", headers=account.csrf)
    with Session(engine) as db:
        actions = [
            r[0]
            for r in db.execute(
                text(
                    "SELECT action FROM audit_events WHERE action LIKE 'resume_theme.%' "
                    "AND actor_user_id = :u ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        ]
    assert actions == ["resume_theme.created", "resume_theme.updated", "resume_theme.deleted"]
