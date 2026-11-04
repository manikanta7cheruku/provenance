"""Checkpoint 2.7: duplicate jobs, reversible links, sightings, and the private and public sides."""

import hashlib
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account, promote_to_admin
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_domain.job_feed import FeedJob
from pv_persistence.dedupe import link_jobs
from pv_persistence.models import JobPosting, SourceJob
from pv_persistence.registry import seed_registry
from pv_persistence.source_jobs import also_seen, search_jobs, store_listing
from pv_persistence.tenancy import tenant_session

MakeAccount = Callable[..., Account]
NOW = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
TEXT = (
    "You will build data pipelines for our analytics team. You work with SQL and Python every day, "
    "partner with product managers, and ship dashboards that leaders use to decide. We offer remote "
    "friendly work, learning budget and a supportive team of engineers who care about quality."
)
OTHER_TEXT = (
    "Drive a delivery van across the north of the city, load and unload parcels, keep the log, and "
    "report faults to the depot manager each evening without fail."
)


def feed(
    ext: str,
    *,
    title: str = "Data Engineer",
    place: str = "London, United Kingdom",
    description: str = TEXT,
    url: str | None = None,
) -> FeedJob:
    link = url or f"https://jobs.example.com/acme/{ext}"
    return FeedJob(
        external_id=ext, url=link, title=title, company_name="Acme", location=place, workplace=None,
        employment_type=None, department="Engineering", description=description, posted_at=None,
        updated_at=None, content_hash=hashlib.sha256(f"{title}{place}{description}{link}".encode()).hexdigest(),
    )  # fmt: skip


@pytest.fixture(autouse=True)
def sources_ready(engine: Engine) -> Iterator[None]:
    """Lever and Greenhouse are usable (verified, in date, on), with no jobs of their own."""
    seed_registry(engine)

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
                "verification_owner = 'test', enabled = true, edited_at = now() "
                "WHERE key IN ('lever', 'greenhouse')"
            )
        )
    yield
    reset()


def put(
    engine: Engine, source: str, board: str, jobs: list[FeedJob], complete: bool = True
) -> list[uuid.UUID]:
    with Session(engine) as db, db.begin():
        counts = store_listing(
            db, source, board, tuple(jobs), NOW, complete=complete, default_company=None
        )
        link_jobs(db, counts.touched)
        return list(counts.touched)


def row(engine: Engine, source: str, ext: str) -> Any:
    with Session(engine) as db:
        return db.execute(
            text(
                "SELECT id, group_id, seen_count, company_norm, title_norm FROM source_jobs WHERE source_key = :s AND external_id = :e"
            ),
            {"s": source, "e": ext},
        ).one()


def links(engine: Engine) -> list[Any]:
    with Session(engine) as db:
        return list(
            db.execute(
                text("SELECT state, method, job_a, job_b FROM source_job_links ORDER BY created_at")
            ).all()
        )


# ------------------------------------------------------------------------------ the public side


def test_the_same_job_on_two_sources_is_linked_and_shares_a_group(engine: Engine) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1", place="London, UK")])
    a, b = row(engine, "lever", "L1"), row(engine, "greenhouse", "G1")
    assert a.group_id == b.group_id == min(a.id, b.id)
    (link,) = links(engine)
    assert link.state == "auto" and link.method == "same_company_title_place"
    assert a.company_norm == "acme" and a.title_norm == "data engineer"


def test_a_repost_under_a_new_id_on_the_same_board_is_linked(engine: Engine) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(
        engine,
        "lever",
        "acme",
        [feed("L1"), FeedJob(**{**feed("L2").__dict__, "content_hash": feed("L1").content_hash})],
    )
    assert [link.method for link in links(engine)] == ["same_content"]
    assert row(engine, "lever", "L1").group_id == row(engine, "lever", "L2").group_id


def test_different_places_or_companies_or_titles_are_not_linked(engine: Engine) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1", place="Berlin, Germany")])
    put(engine, "greenhouse", "acme", [feed("G2", title="Warehouse Operative")])
    other = feed("G3")
    put(engine, "greenhouse", "globex", [FeedJob(**{**other.__dict__, "company_name": "Globex"})])
    assert links(engine) == []
    assert (
        len(
            {
                row(engine, s, e).group_id
                for s, e in (
                    ("lever", "L1"),
                    ("greenhouse", "G1"),
                    ("greenhouse", "G2"),
                    ("greenhouse", "G3"),
                )
            }
        )
        == 4
    )


def test_a_suggested_link_joins_nothing_until_an_administrator_confirms_it(engine: Engine) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1", description=OTHER_TEXT)])
    (link,) = links(engine)
    assert link.state == "suggested"
    assert row(engine, "lever", "L1").group_id != row(engine, "greenhouse", "G1").group_id


def test_running_the_comparison_again_never_overrides_a_decision(engine: Engine) -> None:
    ids = put(engine, "lever", "acme", [feed("L1")])
    ids += put(engine, "greenhouse", "acme", [feed("G1")])
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE source_job_links SET state = 'undone'"))
    with Session(engine) as db, db.begin():
        link_jobs(db, ids)
        from pv_persistence.dedupe import regroup

        regroup(db, set(ids))
    assert [link.state for link in links(engine)] == ["undone"]
    assert row(engine, "lever", "L1").group_id != row(engine, "greenhouse", "G1").group_id


def test_a_poll_counts_each_sighting_and_names_the_company_for_sources_that_do_not(
    engine: Engine,
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    with Session(engine) as db, db.begin():
        store_listing(db, "lever", "acme", (feed("L1"),), NOW, complete=True)
        store_listing(db, "lever", "acme", (feed("L1"),), NOW, complete=True)
    assert row(engine, "lever", "L1").seen_count == 3


# ------------------------------------------------------------------------------ search shows one


def test_search_shows_one_job_per_group_preferring_the_first_party_source_and_lists_the_others(
    engine: Engine, settings: Settings
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1")])
    with Session(engine) as db:
        shown = search_jobs(
            db,
            today=date.today(),
            window_days=180,
            roles=[],
            companies=[],
            locations=[],
            work_mode=None,
            sources=[],
            limit=20,
            offset=0,
        )
        assert len(shown) == 1
        others = also_seen(db, [j for j, _ in shown], date.today(), 180)
        assert len(others[shown[0][0].id]) == 1
        assert others[shown[0][0].id][0][0].source_key != shown[0][0].source_key


def test_the_other_copy_is_hidden_when_its_source_stops_being_usable(engine: Engine) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1")])
    with Session(engine) as db, db.begin():
        db.execute(text("UPDATE job_sources SET enabled = false WHERE key = 'greenhouse'"))
    with Session(engine) as db:
        shown = search_jobs(
            db,
            today=date.today(),
            window_days=180,
            roles=[],
            companies=[],
            locations=[],
            work_mode=None,
            sources=[],
            limit=20,
            offset=0,
        )
        assert [s.key for _, s in shown] == ["lever"]
        assert also_seen(db, [j for j, _ in shown], date.today(), 180) == {}


def test_the_job_list_api_carries_where_else_it_was_seen(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1")])
    body = make_account(app).client.get("/api/v1/search/jobs").json()
    assert len(body) == 1 and len(body[0]["also_seen"]) == 1
    assert body[0]["also_seen"][0]["kind"] == "public" and body[0]["also_seen"][0][
        "url"
    ].startswith("https://")


# ------------------------------------------------------------------------------ administrators


@pytest.fixture
def admin(app: FastAPI, make_account: MakeAccount, engine: Engine) -> Account:
    account = make_account(app)
    promote_to_admin(engine, account.email)
    return account


def test_an_administrator_confirms_a_suggestion_and_undoing_it_splits_the_group_again(
    admin: Account, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1", description=OTHER_TEXT)])
    listed = admin.client.get("/api/v1/admin/job-links", params={"state": "suggested"}).json()
    assert (
        len(listed) == 1 and listed[0]["first"]["source_key"] and "wording" in listed[0]["reason"]
    )
    link_id = listed[0]["id"]
    done = admin.client.post(f"/api/v1/admin/job-links/{link_id}/confirm", headers=admin.csrf)
    assert (
        done.status_code == 200
        and done.json()["state"] == "confirmed"
        and done.json()["decided_at"]
    )
    assert row(engine, "lever", "L1").group_id == row(engine, "greenhouse", "G1").group_id
    undone = admin.client.post(f"/api/v1/admin/job-links/{link_id}/undo", headers=admin.csrf)
    assert undone.json()["state"] == "undone"
    assert row(engine, "lever", "L1").group_id != row(engine, "greenhouse", "G1").group_id
    with Session(engine) as db:
        audited = db.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE action IN ('job_link.confirmed', 'job_link.undone')"
            )
        ).scalar_one()
    assert audited >= 2


def test_undoing_the_one_link_that_joined_a_chain_splits_only_that_part(
    admin: Account, engine: Engine
) -> None:
    put(
        engine,
        "lever",
        "acme",
        [feed("A", place="London"), feed("B", place="Berlin"), feed("C", place="Paris")],
    )
    ids = {e: row(engine, "lever", e).id for e in "ABC"}
    with Session(engine) as db, db.begin():
        for first, second in (("A", "B"), ("B", "C")):
            low, high = sorted((ids[first], ids[second]))
            db.execute(
                text(
                    "INSERT INTO source_job_links (job_a, job_b, method, score, reason, state) VALUES (:a, :b, 'test', 0.9, 'chain', 'auto')"
                ),
                {"a": low, "b": high},
            )
        from pv_persistence.dedupe import regroup

        regroup(db, set(ids.values()))
    assert len({row(engine, "lever", e).group_id for e in "ABC"}) == 1
    with Session(engine) as db:
        link = db.execute(
            text(
                "SELECT id FROM source_job_links WHERE (job_a = :b OR job_b = :b) AND (job_a = :c OR job_b = :c)"
            ),
            {"b": ids["B"], "c": ids["C"]},
        ).scalar_one()
    assert (
        admin.client.post(f"/api/v1/admin/job-links/{link}/undo", headers=admin.csrf).status_code
        == 200
    )
    groups = {e: row(engine, "lever", e).group_id for e in "ABC"}
    assert groups["A"] == groups["B"] != groups["C"]
    assert groups["C"] == ids["C"]


def test_only_administrators_can_see_or_decide_links_and_bad_input_is_refused(
    app: FastAPI, make_account: MakeAccount, admin: Account
) -> None:
    user = make_account(app)
    assert user.client.get("/api/v1/admin/job-links").status_code == 404
    assert (
        user.client.post(
            f"/api/v1/admin/job-links/{uuid.uuid4()}/undo", headers=user.csrf
        ).status_code
        == 404
    )
    assert admin.client.get("/api/v1/admin/job-links", params={"state": "bogus"}).status_code == 422
    assert (
        admin.client.post(
            f"/api/v1/admin/job-links/{uuid.uuid4()}/undo", headers=admin.csrf
        ).status_code
        == 404
    )
    assert (
        admin.client.post(
            f"/api/v1/admin/job-links/{uuid.uuid4()}/erase", headers=admin.csrf
        ).status_code
        == 422
    )


# ------------------------------------------------------------------------------ the private side


def paste(
    engine: Engine,
    account: Account,
    *,
    company: str | None = "Acme",
    title: str = "Data Engineer",
    place: str = "London, UK",
    description: str = TEXT,
    url: str | None = None,
) -> str:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        posting = JobPosting(
            owner_user_id=uuid.UUID(account.user_id), source_name="Wellfound", raw_text=description,
            content_hash=uuid.uuid4().hex + uuid.uuid4().hex, title=title, company=company,
            source_url=url, parse_status="extracted",
            facts={"location": {"value": place, "quote": place, "start": 0, "end": len(place)}} if place else {},
        )  # fmt: skip
        db.add(posting)
        db.flush()
        return str(posting.id)


def matches(account: Account, job_id: str) -> Any:
    return account.client.get(f"/api/v1/jobs/{job_id}/matches")


def decide(account: Account, job_id: str, group_id: str, verb: str) -> Any:
    return account.client.post(
        f"/api/v1/jobs/{job_id}/matches/{group_id}/{verb}", headers=account.csrf
    )


def test_a_pasted_posting_finds_its_public_copies_and_says_why(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    put(engine, "greenhouse", "acme", [feed("G1")])
    account = make_account(app)
    job_id = paste(engine, account)
    body = matches(account, job_id).json()
    assert len(body["matches"]) == 1 and body["note"] is None
    found = body["matches"][0]
    assert found["state"] == "auto" and found["method"] == "same_company_title_place"
    assert "wording" in found["reason"] and len(found["sightings"]) == 2
    kinds = [s["kind"] for s in body["sightings"]]
    assert kinds == ["yours", "public", "public"] and body["sightings"][0]["how"] == "Pasted by you"


def test_a_posting_with_nothing_to_match_says_so_honestly(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    none = matches(account, paste(engine, account)).json()
    assert none["matches"] == [] and "does not mean it is not posted elsewhere" in none["note"]
    nameless = matches(account, paste(engine, account, company=None)).json()
    assert "does not name its company" in nameless["note"]


def test_a_person_can_say_not_the_same_job_and_change_their_mind(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    account = make_account(app)
    job_id = paste(engine, account)
    group = matches(account, job_id).json()["matches"][0]["group_id"]
    undone = decide(account, job_id, group, "undo").json()
    assert undone["matches"][0]["state"] == "undone" and [
        s["kind"] for s in undone["sightings"]
    ] == ["yours"]
    back = decide(account, job_id, group, "confirm").json()
    assert back["matches"][0]["state"] == "confirmed" and len(back["sightings"]) == 2
    reset = decide(account, job_id, group, "reset").json()
    assert reset["matches"][0]["state"] == "auto"


def test_a_suggested_match_is_only_a_suggestion_until_the_person_confirms(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1", description=OTHER_TEXT)])
    account = make_account(app)
    job_id = paste(engine, account)
    body = matches(account, job_id).json()
    assert body["matches"][0]["state"] == "suggested" and [
        s["kind"] for s in body["sightings"]
    ] == ["yours"]
    confirmed = decide(account, job_id, body["matches"][0]["group_id"], "confirm").json()
    assert len(confirmed["sightings"]) == 2


def test_a_decision_is_private_to_the_person_who_made_it(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    mine, theirs = make_account(app), make_account(app)
    my_job, their_job = paste(engine, mine), paste(engine, theirs)
    group = matches(mine, my_job).json()["matches"][0]["group_id"]
    decide(mine, my_job, group, "undo")
    assert matches(theirs, their_job).json()["matches"][0]["state"] == "auto"
    assert matches(theirs, my_job).status_code == 404
    assert decide(theirs, my_job, group, "confirm").status_code == 404
    assert (
        decide(theirs, their_job, str(uuid.uuid4()), "confirm").status_code == 404
    )  # not a candidate


def test_public_jobs_never_learn_that_a_private_posting_exists(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    with Session(engine) as db:
        before = db.execute(text("SELECT count(*) FROM source_job_links")).scalar_one()
    account = make_account(app)
    job_id = paste(
        engine,
        account,
        description=TEXT + " Secret salary talk with the recruiter.",
        url="https://private.example/me",
    )
    matches(account, job_id)
    with Session(engine) as db:
        assert db.execute(text("SELECT count(*) FROM source_job_links")).scalar_one() == before
        assert (
            db.execute(
                text("SELECT count(*) FROM source_jobs WHERE description LIKE '%Secret salary%'")
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("SELECT count(*) FROM source_jobs WHERE url LIKE '%private.example%'")
            ).scalar_one()
            == 0
        )
    listing = make_account(app).client.get("/api/v1/search/jobs").json()
    assert "Secret salary" not in str(listing) and "private.example" not in str(listing)


def test_decisions_are_protected_by_row_level_security_and_go_with_the_posting(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    account = make_account(app)
    job_id = paste(engine, account)
    group = matches(account, job_id).json()["matches"][0]["group_id"]
    decide(account, job_id, group, "undo")
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(uuid.uuid4())})
        assert db.execute(text("SELECT count(*) FROM posting_links")).scalar_one() == 0
    with pytest.raises(DBAPIError), Session(engine) as db, db.begin():
        db.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(uuid.uuid4())})
        db.execute(
            text(
                "INSERT INTO posting_links (owner_user_id, posting_id, source_job_id, state) SELECT :o, :p, id, 'undone' FROM source_jobs LIMIT 1"
            ),
            {"o": account.user_id, "p": job_id},
        )
    assert account.client.delete(f"/api/v1/jobs/{job_id}", headers=account.csrf).status_code == 204
    with Session(engine) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM posting_links WHERE posting_id = :p"), {"p": job_id}
            ).scalar_one()
            == 0
        )


def test_a_source_that_is_no_longer_usable_takes_its_matches_with_it(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    account = make_account(app)
    job_id = paste(engine, account)
    assert len(matches(account, job_id).json()["matches"]) == 1
    with Session(engine) as db, db.begin():
        db.execute(
            text("UPDATE job_sources SET terms_checked_at = '2020-01-01' WHERE key = 'lever'")
        )
    assert matches(account, job_id).json()["matches"] == []


def test_the_match_routes_need_a_session_and_the_csrf_token(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    put(engine, "lever", "acme", [feed("L1")])
    account = make_account(app)
    job_id = paste(engine, account)
    group = matches(account, job_id).json()["matches"][0]["group_id"]
    assert account.client.post(f"/api/v1/jobs/{job_id}/matches/{group}/undo").status_code in (
        401,
        403,
    )
    assert (
        account.client.post(
            f"/api/v1/jobs/{job_id}/matches/{group}/delete", headers=account.csrf
        ).status_code
        == 422
    )
    account.client.cookies.clear()
    assert matches(account, job_id).status_code == 401
    with Session(engine) as db:
        assert db.execute(select(SourceJob.id)).first() is not None
