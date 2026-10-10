"""Tenant isolation. User A must never read or change user B's data.

Two independent layers are tested separately: the API (owner filter, 404 semantics)
and the database (Row Level Security through raw SQL as the application role).
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from helpers import Account, promote_to_admin
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

pytestmark = pytest.mark.integration

MakeAccount = Callable[..., Account]
ENTRIES = "/api/v1/profile/entries"


def create_entry(account: Account, name: str = "Python") -> str:
    response = account.client.post(
        ENTRIES, json={"entry_type": "skill", "data": {"name": name}}, headers=account.csrf
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_owner_can_create_read_update_and_delete(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    entry_id = create_entry(account)
    assert account.client.get(f"{ENTRIES}/{entry_id}").json()["data"] == {"name": "Python"}

    updated = account.client.patch(
        f"{ENTRIES}/{entry_id}", json={"data": {"name": "Python 3"}}, headers=account.csrf
    )
    assert updated.status_code == 200
    assert updated.json()["user_edited"] is True

    assert account.client.delete(f"{ENTRIES}/{entry_id}", headers=account.csrf).status_code == 204
    assert account.client.get(f"{ENTRIES}/{entry_id}").status_code == 404


def test_other_users_get_404_on_every_operation(app: FastAPI, make_account: MakeAccount) -> None:
    owner, intruder = make_account(app), make_account(app)
    entry_id = create_entry(owner)

    assert intruder.client.get(f"{ENTRIES}/{entry_id}").status_code == 404
    assert (
        intruder.client.patch(
            f"{ENTRIES}/{entry_id}", json={"data": {"name": "hijacked"}}, headers=intruder.csrf
        ).status_code
        == 404
    )
    assert intruder.client.delete(f"{ENTRIES}/{entry_id}", headers=intruder.csrf).status_code == 404
    assert intruder.client.get(ENTRIES).json() == []

    still_there = owner.client.get(f"{ENTRIES}/{entry_id}").json()
    assert still_there["data"] == {"name": "Python"}
    assert still_there["user_edited"] is False


def test_unknown_and_foreign_ids_look_identical(app: FastAPI, make_account: MakeAccount) -> None:
    owner, intruder = make_account(app), make_account(app)
    foreign = intruder.client.get(f"{ENTRIES}/{create_entry(owner)}")
    unknown = intruder.client.get(f"{ENTRIES}/{uuid.uuid4()}")
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["code"] == unknown.json()["code"]
    assert foreign.json()["message"] == unknown.json()["message"]


def test_client_cannot_choose_the_owner(app: FastAPI, make_account: MakeAccount) -> None:
    victim, attacker = make_account(app), make_account(app)
    response = attacker.client.post(
        ENTRIES,
        json={"entry_type": "skill", "data": {}, "owner_user_id": victim.user_id},
        headers=attacker.csrf,
    )
    assert response.status_code == 201
    created_id = response.json()["id"]
    assert [row["id"] for row in victim.client.get(ENTRIES).json()] == []
    assert created_id in [row["id"] for row in attacker.client.get(ENTRIES).json()]


def test_admin_cannot_read_user_data(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    user, admin = make_account(app), make_account(app)
    entry_id = create_entry(user)
    promote_to_admin(engine, admin.email)
    assert admin.client.get(f"{ENTRIES}/{entry_id}").status_code == 404
    assert admin.client.get(ENTRIES).json() == []


def tenant_rows(engine: Engine, user_id: str | None) -> list[str]:
    with engine.connect() as conn, conn.begin():
        if user_id is not None:
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": user_id})
        return [str(r[0]) for r in conn.execute(text("SELECT owner_user_id FROM profile_entries"))]


def test_row_level_security_filters_raw_sql(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    a, b = make_account(app), make_account(app)
    create_entry(a)
    create_entry(b)

    rows_a = tenant_rows(engine, a.user_id)
    rows_b = tenant_rows(engine, b.user_id)
    assert rows_a and set(rows_a) == {a.user_id}
    assert rows_b and set(rows_b) == {b.user_id}
    assert tenant_rows(engine, None) == []  # no tenant context: fail closed
    assert tenant_rows(engine, str(uuid.uuid4())) == []  # unknown tenant sees nothing


def test_row_level_security_blocks_writing_for_another_tenant(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    a, b = make_account(app), make_account(app)
    with engine.connect() as conn, pytest.raises(ProgrammingError), conn.begin():
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": a.user_id})
        conn.execute(
            text("INSERT INTO profile_entries (owner_user_id, entry_type) VALUES (:o, 'skill')"),
            {"o": b.user_id},
        )


def test_tenant_context_does_not_leak_between_transactions(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    a = make_account(app)
    create_entry(a)
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": a.user_id})
            assert conn.execute(text("SELECT count(*) FROM profile_entries")).scalar_one() >= 1
        with conn.begin():  # same connection, new transaction, no context set
            assert conn.execute(text("SELECT count(*) FROM profile_entries")).scalar_one() == 0
