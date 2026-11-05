"""Checkpoint 2.9: the workbench. Decisions and their log, notes, the list and its filters, bulk
moves, saved views, and adding a job found on a source."""

import hashlib
import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from table_helpers import LONG

from pv_domain.job_feed import FeedJob
from pv_persistence.registry import seed_registry
from pv_persistence.source_jobs import store_listing
from pv_persistence.tenancy import tenant_session

JOBS = "/api/v1/jobs"
BENCH = "/api/v1/workbench"
PREFS = "/api/v1/profile/preferences"
MakeAccount = Callable[..., Account]
NOW = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


def add(account: Account, title: str, company: str = "Acme", **extra: Any) -> str:
    response = account.client.post(
        f"{JOBS}/manual",
        json={"title": title, "company": company, "description": f"{LONG} {title}", **extra},
        headers=account.csrf,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["job"]["id"])


def read_as(engine: Engine, account: Account, job_id: str, **facts: str) -> None:
    """Make a posting look as if it had been read, with the given facts (value only)."""
    payload = {k: {"value": v, "quote": f"{k} {v}"} for k, v in facts.items()}
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(
            text(
                "UPDATE job_postings SET parse_status = 'extracted', facts = CAST(:f AS jsonb), "
                "extracted_at = now() WHERE id = :i"
            ),
            {"f": json.dumps(payload), "i": job_id},
        )


def decide(account: Account, job_id: str, action: str, **extra: Any) -> Any:
    return account.client.post(
        f"{JOBS}/{job_id}/decision", json={"action": action, **extra}, headers=account.csrf
    )


def bench(account: Account, **params: Any) -> Any:
    response = account.client.get(BENCH, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def titles(body: Any) -> list[str]:
    return [r["title"] for r in body["rows"]]


def state_of(account: Account, job_id: str) -> str:
    return str(account.client.get(f"{JOBS}/{job_id}").json()["decision"]["state"])


# --------------------------------------------------------------------- the schema


def test_the_tables_have_forced_security_and_sane_checks(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    uid = uuid.UUID(account.user_id)
    job_id = add(account, "Backend engineer")
    with Session(engine) as db:
        flags = {
            r.relname: (r.relrowsecurity, r.relforcerowsecurity)
            for r in db.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN "
                    "('job_decisions', 'job_decision_events', 'workbench_views')"
                )
            )
        }
    assert flags == {
        "job_decisions": (True, True),
        "job_decision_events": (True, True),
        "workbench_views": (True, True),
    }
    bad = {
        "an unknown state": "INSERT INTO job_decisions (posting_id, owner_user_id, state) VALUES (:p, :u, 'submitted')",
        "applied with no date": "INSERT INTO job_decisions (posting_id, owner_user_id, state) VALUES (:p, :u, 'applied')",
        "a note that is too long": "INSERT INTO job_decisions (posting_id, owner_user_id, note) VALUES (:p, :u, repeat('x', 2001))",
        "an unknown action": "INSERT INTO job_decision_events (posting_id, owner_user_id, action, from_state, to_state) VALUES (:p, :u, 'submit', 'new', 'saved')",
        "an empty view name": "INSERT INTO workbench_views (owner_user_id, name) VALUES (:u, '')",
        "another way of acquiring": "UPDATE job_postings SET acquisition_method = 'scraped'",
    }
    for name, sql in bad.items():
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(sql), {"p": job_id, "u": str(uid)})
        assert name
    with tenant_session(engine, uid) as db:  # a posting made from a source is allowed
        db.execute(
            text("UPDATE job_postings SET acquisition_method = 'source_job' WHERE id = :p"),
            {"p": job_id},
        )


# --------------------------------------------------------------------- decisions


def test_a_job_is_new_until_the_person_acts(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    decision = account.client.get(f"{JOBS}/{job_id}").json()["decision"]
    assert decision["state"] == "new" and decision["state_label"] == "New"
    assert [a["action"] for a in decision["actions"]] == [
        "save",
        "approve",
        "mark_applied",
        "dismiss",
    ]
    assert decision["note"] == "" and decision["applied_at"] is None


def test_saving_and_unsaving(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    saved = decide(account, job_id, "save")
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["decision"]["state"] == "saved"
    assert (body["undo"], body["undo_label"]) == ("unsave", "Unsave")
    assert [a["action"] for a in body["decision"]["actions"]][0] == "unsave"
    back = decide(account, job_id, "unsave").json()
    assert back["decision"]["state"] == "new" and back["undo"] is None


def test_dismissing_hides_it_from_the_active_view_and_undo_brings_it_back(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    result = decide(account, job_id, "dismiss").json()
    assert result["undo"] == "undo_dismiss"
    assert titles(bench(account)) == [] and titles(bench(account, view="dismissed")) == [
        "Backend engineer"
    ]
    decide(account, job_id, "undo_dismiss")
    assert titles(bench(account)) == ["Backend engineer"]


def test_applying_records_the_day_and_undo_returns_the_job_to_where_it_was(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    decide(account, job_id, "save")
    decide(account, job_id, "approve")
    applied = decide(account, job_id, "mark_applied", applied_on="2026-10-30").json()
    assert applied["decision"]["state"] == "applied"
    assert applied["decision"]["applied_at"].startswith("2026-10-30")
    assert applied["undo"] == "undo_applied"
    assert titles(bench(account, view="applications")) == ["Backend engineer"]
    undone = decide(account, job_id, "undo_applied").json()
    assert (
        undone["decision"]["state"] == "approved_for_prep"
        and undone["decision"]["applied_at"] is None
    )


def test_applied_with_no_day_given_means_today_and_a_future_day_is_refused(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    future = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    refused = decide(account, job_id, "mark_applied", applied_on=future)
    assert refused.status_code == 422 and "future" in refused.json()["fields"]["applied_on"]
    assert state_of(account, job_id) == "new"
    ok = decide(account, job_id, "mark_applied").json()
    assert ok["decision"]["applied_at"].startswith(datetime.now(UTC).date().isoformat())


def test_a_move_that_is_not_allowed_is_refused_in_words_and_changes_nothing(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    refused = decide(account, job_id, "undo_dismiss")
    assert refused.status_code == 409
    assert (
        refused.json()["code"] == "DECISION_NOT_ALLOWED"
        and "not available" in refused.json()["message"]
    )
    assert state_of(account, job_id) == "new"
    decide(account, job_id, "mark_applied")
    assert decide(account, job_id, "save").status_code == 409
    assert decide(account, job_id, "bogus").status_code == 422


def test_a_job_a_hard_rule_rules_out_cannot_be_approved(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    job_id = add(account, "Visa job")
    read_as(engine, account, job_id, sponsorship="not_offered")
    account.client.put(
        PREFS,
        json={"needs_sponsorship": True, "authorized_countries": ["India"]},
        headers=account.csrf,
    )
    detail = account.client.get(f"{JOBS}/{job_id}").json()
    assert detail["eligibility"] == "not_eligible"
    assert "approve" not in [a["action"] for a in detail["decision"]["actions"]]
    refused = decide(account, job_id, "approve")
    assert refused.status_code == 409 and refused.json()["code"] == "NOT_ELIGIBLE"
    assert decide(account, job_id, "save").status_code == 200


def test_every_move_is_logged_without_any_note_text(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    account.client.put(f"{JOBS}/{job_id}/note", json={"note": "secret plan"}, headers=account.csrf)
    for action in ("save", "approve", "mark_applied", "undo_applied"):
        decide(account, job_id, action)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        moves = list(
            db.execute(
                text(
                    "SELECT action, from_state, to_state FROM job_decision_events ORDER BY created_at"
                )
            )
        )
        assert [(m.action, m.from_state, m.to_state) for m in moves] == [
            ("save", "new", "saved"),
            ("approve", "saved", "approved_for_prep"),
            ("mark_applied", "approved_for_prep", "applied"),
            ("undo_applied", "applied", "approved_for_prep"),
        ]
        columns = [
            c[0] for c in db.execute(text("SELECT * FROM job_decision_events")).cursor.description
        ]  # type: ignore[union-attr]
    assert "note" not in columns
    with Session(engine) as db:
        audit = list(
            db.execute(
                text(
                    "SELECT action, metadata FROM audit_events WHERE actor_user_id = :u AND action = 'job.decision' ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        )
    assert [a.metadata["decision"] for a in audit] == [
        "save",
        "approve",
        "mark_applied",
        "undo_applied",
    ]
    assert "secret plan" not in json.dumps([a.metadata for a in audit])


def test_decisions_belong_to_their_owner(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    owner, other = make_account(app), make_account(app)
    job_id = add(owner, "Backend engineer")
    decide(owner, job_id, "save")
    assert decide(other, job_id, "dismiss").status_code == 404
    assert (
        other.client.put(
            f"{JOBS}/{job_id}/note", json={"note": "x"}, headers=other.csrf
        ).status_code
        == 404
    )
    assert other.client.get(BENCH).json()["rows"] == []
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:
        for table in ("job_decisions", "job_decision_events", "workbench_views"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608
    assert state_of(owner, job_id) == "saved"
    assert decide(owner, str(uuid.uuid4()), "save").status_code == 404


def test_deleting_a_job_removes_its_decision_and_log(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    decide(account, job_id, "save")
    assert account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf).status_code == 204
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM job_decisions")).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM job_decision_events")).scalar_one() == 0


def test_decisions_need_a_signed_in_writer(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    assert account.client.post(
        f"{JOBS}/{job_id}/decision", json={"action": "save"}
    ).status_code in (401, 403)
    account.client.cookies.clear()
    assert decide(account, job_id, "save").status_code == 401
    assert account.client.get(BENCH).status_code == 401


# --------------------------------------------------------------------- notes


def test_a_note_is_kept_through_every_move_and_is_searchable(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    other_id = add(account, "Data analyst")
    saved = account.client.put(
        f"{JOBS}/{job_id}/note", json={"note": "  Referred by Priya\x00  "}, headers=account.csrf
    )
    assert saved.status_code == 200 and saved.json()["note"] == "Referred by Priya"
    assert saved.json()["state"] == "new"
    decide(account, job_id, "save")
    decide(account, job_id, "mark_applied")
    assert account.client.get(f"{JOBS}/{job_id}").json()["decision"]["note"] == "Referred by Priya"
    body = bench(account, view="all", q="priya")
    assert titles(body) == ["Backend engineer"] and body["rows"][0]["has_note"] is True
    noted = {r["title"]: r["has_note"] for r in bench(account, view="all")["rows"]}
    assert noted == {"Backend engineer": True, "Data analyst": False}
    assert other_id


def test_a_note_can_be_cleared_and_has_a_limit(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    account.client.put(f"{JOBS}/{job_id}/note", json={"note": "keep"}, headers=account.csrf)
    cleared = account.client.put(f"{JOBS}/{job_id}/note", json={"note": ""}, headers=account.csrf)
    assert cleared.json()["note"] == ""
    long = account.client.put(
        f"{JOBS}/{job_id}/note", json={"note": "x" * 2001}, headers=account.csrf
    )
    assert long.status_code == 422
    assert (
        account.client.put(
            f"{JOBS}/{job_id}/note", json={"note": "x", "extra": 1}, headers=account.csrf
        ).status_code
        == 422
    )


# --------------------------------------------------------------------- the list


def seeded(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> tuple[Account, dict[str, str]]:
    account = make_account(app)
    ids = {
        "backend": add(account, "Backend engineer", "Acme"),
        "data": add(account, "Data analyst", "Beta Labs", source_name="Naukri"),
        "front": add(account, "Frontend developer", ""),
        "platform": add(account, "Platform engineer", "Acme"),
        "sre": add(account, "SRE", "Gamma"),
    }
    read_as(
        engine,
        account,
        ids["backend"],
        work_mode="remote",
        location="Pune, India",
        seniority="mid",
        employment_type="full_time",
    )
    read_as(
        engine,
        account,
        ids["data"],
        work_mode="hybrid",
        location="Bengaluru, India",
        seniority="entry",
        employment_type="internship",
    )
    return account, ids


def test_the_list_filters_sorts_and_counts(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, ids = seeded(app, make_account, engine)
    decide(account, ids["platform"], "dismiss")
    decide(account, ids["sre"], "mark_applied")
    decide(account, ids["front"], "save")

    body = bench(account)
    assert set(titles(body)) == {"Backend engineer", "Data analyst", "Frontend developer"}
    assert body["total"] == 3 and body["truncated"] is False
    assert body["facets"]["views"] == {
        "active": 3,
        "saved": 1,
        "applications": 1,
        "dismissed": 1,
        "archived": 0,
        "all": 5,
    }
    assert body["facets"]["work_modes"] == {"remote": 1, "hybrid": 1}
    assert body["facets"]["sources"]["Naukri"] == 1

    assert titles(bench(account, work_mode="hybrid")) == ["Data analyst"]
    assert titles(bench(account, work_mode=["remote", "hybrid"], sort="title")) == [
        "Backend engineer",
        "Data analyst",
    ]
    assert titles(bench(account, seniority="entry")) == ["Data analyst"]
    assert titles(bench(account, employment_type="internship")) == ["Data analyst"]
    assert titles(bench(account, source="Naukri")) == ["Data analyst"]
    assert titles(bench(account, company="beta")) == ["Data analyst"]
    assert titles(bench(account, location="pune")) == ["Backend engineer"]
    assert titles(bench(account, q="engineer")) == ["Backend engineer"]
    assert titles(bench(account, view="all", q="engineer", sort="title")) == [
        "Backend engineer",
        "Platform engineer",
    ]
    assert titles(bench(account, view="saved")) == ["Frontend developer"]
    assert titles(bench(account, state=["dismissed", "applied"], sort="title")) == [
        "Platform engineer",
        "SRE",
    ]
    assert bench(account, work_mode="remote")["rows"][0]["decision"]["state"] == "new"


def test_sorting_newest_first_by_default_and_either_way(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, _ = seeded(app, make_account, engine)
    newest = titles(bench(account, view="all"))
    assert newest[0] == "SRE" and newest[-1] == "Backend engineer"
    assert titles(bench(account, view="all", sort="added", desc="false")) == list(reversed(newest))
    by_company = [r["company"] for r in bench(account, view="all", sort="company")["rows"]]
    assert by_company == ["Acme", "Acme", "Beta Labs", "Gamma", None]  # no company last


def test_unknown_filter_values_are_dropped_not_guessed_at(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, _ = seeded(app, make_account, engine)
    body = bench(
        account,
        view="nonsense",
        sort="nonsense",
        work_mode="moon",
        band="gold",
        eligibility="maybe",
    )
    assert body["query"] == {"view": "active", "sort": "added"}
    assert body["total"] == 5


def test_the_fit_band_is_the_one_the_job_page_shows(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, ids = seeded(app, make_account, engine)
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        req = db.execute(
            text(
                "INSERT INTO job_requirements (posting_id, owner_user_id, ordinal, text, kind, category, quote, quote_start, quote_end) "
                "VALUES (:p, :u, 0, 'Python', 'required', 'skill', 'Python', 0, 6) RETURNING id"
            ),
            {"p": ids["backend"], "u": str(uid)},
        ).scalar_one()
        analysis = db.execute(
            text(
                "INSERT INTO job_analyses (owner_user_id, posting_id, status) VALUES (:u, :p, 'complete') RETURNING id"
            ),
            {"u": str(uid), "p": ids["backend"]},
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO requirement_verdicts (owner_user_id, analysis_id, requirement_id, verdict, evidence_kind) VALUES (:u, :a, :r, 'met', 'direct')"
            ),
            {"u": str(uid), "a": analysis, "r": req},
        )
    body = bench(account, band="strong")
    assert titles(body) == ["Backend engineer"] and body["rows"][0]["band"] == "strong"
    assert body["facets"]["bands"] == {"strong": 1}
    assert [r["band"] for r in bench(account, sort="fit")["rows"]][0] == "strong"
    assert [r["band"] for r in bench(account, sort="fit")["rows"]][-1] is None  # no check yet, last
    page = account.client.get(f"{JOBS}/{ids['backend']}/analysis").json()
    assert page["score"]["band"] == "strong"  # the same answer the job page gives


def test_a_big_list_is_cut_and_says_so(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        for i in range(502):
            digest = hashlib.sha256(str(i).encode()).hexdigest()
            db.execute(
                text(
                    "INSERT INTO job_postings (owner_user_id, source_name, raw_text, content_hash, title) "
                    "VALUES (:u, 'Other', :t, :h, :title)"
                ),
                {"u": account.user_id, "t": LONG + str(i), "h": digest, "title": f"Job {i:03d}"},
            )
    body = bench(account, sort="title")
    assert body["truncated"] is True and len(body["rows"]) == 500


# --------------------------------------------------------------------- bulk


def test_a_bulk_move_does_what_it_can_and_says_what_it_could_not(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, ids = seeded(app, make_account, engine)
    decide(account, ids["data"], "save")
    stranger = str(uuid.uuid4())
    body = account.client.post(
        f"{BENCH}/bulk",
        json={"ids": [ids["backend"], ids["data"], ids["front"], stranger], "action": "save"},
        headers=account.csrf,
    ).json()
    assert (body["done"], body["skipped"]) == (2, 2)
    by_id = {r["id"]: r for r in body["results"]}
    assert by_id[ids["backend"]]["ok"] and by_id[ids["backend"]]["state"] == "saved"
    assert not by_id[ids["data"]]["ok"] and "not available" in by_id[ids["data"]]["message"]
    assert by_id[stranger]["message"] == "Not found."
    assert (body["undo"], body["undo_label"]) == ("unsave", "Unsave")
    assert state_of(account, ids["front"]) == "saved"
    undone = account.client.post(
        f"{BENCH}/bulk",
        json={"ids": [ids["backend"], ids["front"]], "action": body["undo"]},
        headers=account.csrf,
    ).json()
    assert undone["done"] == 2 and state_of(account, ids["backend"]) == "new"


def test_a_bulk_move_cannot_touch_another_persons_jobs(
    app: FastAPI, make_account: MakeAccount
) -> None:
    owner, other = make_account(app), make_account(app)
    job_id = add(owner, "Backend engineer")
    body = other.client.post(
        f"{BENCH}/bulk", json={"ids": [job_id], "action": "dismiss"}, headers=other.csrf
    ).json()
    assert (
        body["done"] == 0 and body["results"][0]["message"] == "Not found." and body["undo"] is None
    )
    assert state_of(owner, job_id) == "new"


def test_bulk_requests_are_bounded_and_checked(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    same = str(uuid.uuid4())
    for payload in (
        {"ids": [], "action": "save"},
        {"ids": [str(uuid.uuid4()) for _ in range(101)], "action": "save"},
        {"ids": [same, same], "action": "save"},
        {"ids": [same], "action": "bogus"},
        {"ids": ["not-a-uuid"], "action": "save"},
    ):
        assert (
            account.client.post(f"{BENCH}/bulk", json=payload, headers=account.csrf).status_code
            == 422
        )


def test_a_bulk_approve_skips_the_job_a_hard_rule_rules_out(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    ok, blocked = add(account, "Fine job"), add(account, "Visa job")
    read_as(engine, account, blocked, sponsorship="not_offered")
    account.client.put(
        PREFS,
        json={"needs_sponsorship": True, "authorized_countries": ["India"]},
        headers=account.csrf,
    )
    body = account.client.post(
        f"{BENCH}/bulk", json={"ids": [ok, blocked], "action": "approve"}, headers=account.csrf
    ).json()
    assert (body["done"], body["skipped"]) == (1, 1)
    assert "hard requirement" in next(r for r in body["results"] if not r["ok"])["message"]
    assert body["undo"] is None  # approving is not taken back


# --------------------------------------------------------------------- saved views


def test_saved_views_are_kept_cleaned_and_private(app: FastAPI, make_account: MakeAccount) -> None:
    owner, other = make_account(app), make_account(app)
    made = owner.client.post(
        f"{BENCH}/views",
        json={
            "name": "  Remote  roles ",
            "query": {"view": "saved", "work_modes": ["remote", "moon"], "sort": "fit", "junk": 1},
        },
        headers=owner.csrf,
    )
    assert made.status_code == 201, made.text
    view = made.json()
    assert view["name"] == "Remote roles"
    assert view["query"] == {"view": "saved", "sort": "fit", "work_modes": ["remote"]}
    assert [v["id"] for v in owner.client.get(f"{BENCH}/views").json()] == [view["id"]]
    assert other.client.get(f"{BENCH}/views").json() == []
    assert other.client.delete(f"{BENCH}/views/{view['id']}", headers=other.csrf).status_code == 404
    assert owner.client.delete(f"{BENCH}/views/{view['id']}", headers=owner.csrf).status_code == 204
    assert owner.client.get(f"{BENCH}/views").json() == []
    assert owner.client.delete(f"{BENCH}/views/{view['id']}", headers=owner.csrf).status_code == 404


def test_a_saved_views_query_gives_the_same_list_when_used(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account, _ = seeded(app, make_account, engine)
    view = account.client.post(
        f"{BENCH}/views",
        json={"name": "Remote", "query": {"work_modes": ["remote"], "sort": "title"}},
        headers=account.csrf,
    ).json()
    q = view["query"]
    assert titles(bench(account, view=q["view"], work_mode=q["work_modes"], sort=q["sort"])) == [
        "Backend engineer"
    ]


def test_view_names_are_unique_without_regard_to_case_and_limited_in_number(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)

    def post(name: str) -> Any:
        return account.client.post(
            f"{BENCH}/views", json={"name": name, "query": {}}, headers=account.csrf
        )

    assert post("Remote").status_code == 201
    taken = post("remote")
    assert taken.status_code == 409 and taken.json()["code"] == "VIEW_NAME_TAKEN"
    for i in range(19):
        assert post(f"View {i}").status_code == 201
    full = post("One too many")
    assert full.status_code == 422 and "20 saved views" in full.json()["message"]


def test_view_input_is_checked(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    for payload in (
        {"name": "", "query": {}},
        {"name": "   ", "query": {}},
        {"name": "x" * 61, "query": {}},
        {"name": "ok", "query": {"company": "x" * 5000}},
        {"name": "ok", "extra": 1},
    ):
        assert (
            account.client.post(f"{BENCH}/views", json=payload, headers=account.csrf).status_code
            == 422
        )


# --------------------------------------------------------------------- a job found on a source


@pytest.fixture
def sources_ready(engine: Engine) -> Iterator[None]:
    def reset() -> None:
        with Session(engine) as db, db.begin():
            db.execute(text("DELETE FROM source_jobs"))
            db.execute(text("DELETE FROM tasks WHERE task_type = 'poll_source'"))
            db.execute(text("UPDATE job_sources SET edited_at = NULL"))
        seed_registry(engine)

    reset()
    with Session(engine) as db, db.begin():
        db.execute(
            text(
                "UPDATE job_sources SET compliance_status = 'verified', terms_checked_at = current_date, "
                "verification_owner = 'test', enabled = true, edited_at = now() WHERE key = 'lever'"
            )
        )
    yield
    reset()


def source_job(engine: Engine, ext: str = "L1", description: str = LONG) -> str:
    link = f"https://jobs.lever.co/acme/{ext}"
    job = FeedJob(
        external_id=ext, url=link, title="Data Engineer", company_name="Acme", location="London, UK",
        workplace=None, employment_type=None, department="Eng", description=description, posted_at=None,
        updated_at=None, content_hash=hashlib.sha256(f"{ext}{description}".encode()).hexdigest(),
    )  # fmt: skip
    with Session(engine) as db, db.begin():
        store_listing(db, "lever", "acme", (job,), NOW, complete=True, default_company=None)
        return str(
            db.execute(
                text("SELECT id FROM source_jobs WHERE external_id = :e"), {"e": ext}
            ).scalar_one()
        )


def test_a_job_found_on_a_source_becomes_a_private_posting_that_can_be_tracked(
    app: FastAPI, make_account: MakeAccount, engine: Engine, sources_ready: None
) -> None:
    account = make_account(app)
    found = source_job(engine)
    made = account.client.post(f"/api/v1/search/jobs/{found}/add", headers=account.csrf)
    assert made.status_code == 201, made.text
    job = made.json()["job"]
    assert job["acquisition_method"] == "source_job" and job["visibility"] == "private"
    assert job["source_url"] == "https://jobs.lever.co/acme/L1"
    assert (job["title"], job["company"]) == ("Data Engineer", "Acme")
    assert state_of(account, job["id"]) == "new"
    again = account.client.post(f"/api/v1/search/jobs/{found}/add", headers=account.csrf)
    assert (
        again.status_code == 200
        and again.json()["duplicate"] is True
        and again.json()["job"]["id"] == job["id"]
    )
    other = make_account(app)
    mine = other.client.post(f"/api/v1/search/jobs/{found}/add", headers=other.csrf)
    assert (
        mine.status_code == 201 and mine.json()["job"]["id"] != job["id"]
    )  # everyone gets their own copy
    # It matches its own public job on read, so the job page says where else it appears.
    matches = account.client.get(f"{JOBS}/{job['id']}/matches").json()
    assert any(
        s["url"] == "https://jobs.lever.co/acme/L1"
        for m in matches["matches"]
        for s in m["sightings"]
    )


def test_a_listing_that_cannot_be_added_says_why(
    app: FastAPI, make_account: MakeAccount, engine: Engine, sources_ready: None
) -> None:
    account = make_account(app)
    short = source_job(engine, "S1", description="Too short to read.")
    refused = account.client.post(f"/api/v1/search/jobs/{short}/add", headers=account.csrf)
    assert refused.status_code == 422 and "paste it instead" in refused.json()["message"]
    closed = source_job(engine, "C1")
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE source_jobs SET closed_at = now() WHERE id = :i"), {"i": closed})
    assert (
        account.client.post(f"/api/v1/search/jobs/{closed}/add", headers=account.csrf).status_code
        == 404
    )
    live = source_job(engine, "V1")
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE job_sources SET enabled = false WHERE key = 'lever'"))
    assert (
        account.client.post(f"/api/v1/search/jobs/{live}/add", headers=account.csrf).status_code
        == 404
    )
    assert (
        account.client.post(
            f"/api/v1/search/jobs/{uuid.uuid4()}/add", headers=account.csrf
        ).status_code
        == 404
    )


def test_date_helpers_are_not_needed_for_the_day_of_applying(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = add(account, "Backend engineer")
    today = datetime.now(UTC).date().isoformat()  # the server decides in UTC
    assert decide(account, job_id, "mark_applied", applied_on=today).status_code == 200
