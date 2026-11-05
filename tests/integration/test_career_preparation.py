"""Checkpoint 3.2: career preparation with the real database. What to prepare and why, the plan,
practice material the model writes and code checks, a message to send, and a mock interview."""

import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_tailoring import checked_job

from pv_config import Settings
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.prepare_job import run_prepare

JOBS = "/api/v1/jobs"
MakeAccount = Callable[..., Account]


class PrepStub:
    """Stands in for the model. `mode` says what it writes from the first evidence it is shown."""

    name = "stub"

    def __init__(self, mode: str = "good") -> None:
        self.mode = mode
        self.prompts: list[str] = []

    def list_models(self) -> list[Any]:
        return []

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError

    def generate(self, *, prompt: str, **_: Any) -> GenerationResult:
        self.prompts.append(prompt)
        found = re.search(r"^E1: (.*)$", prompt, flags=re.MULTILINE)
        first = found.group(1) if found else ""
        single = "Write one item." in prompt
        if self.mode == "garbage":
            return GenerationResult(
                text="not json at all", input_tokens=5, output_tokens=5, latency_ms=1
            )
        if single:
            message = {
                "short": "Hi.",
                "invented": f"I worked with this: {first} I also run Kubernetes for 400 users at Google.",
            }.get(self.mode, f"I worked with this in my internship: {first}")
            body: dict[str, Any] = {
                "items": [{"text": message, "evidence": ["E1"] if first else []}]
            }
        elif self.mode == "invented":
            body = {
                "items": [
                    {
                        "text": "How did you use this?",
                        "guidance": f"{first} I also ran Kubernetes clusters for 400 users at Google.",
                        "requirement": "R1",
                        "evidence": ["E1"],
                    }
                ]
            }
        else:
            body = {
                "items": [
                    {
                        "text": "Tell me about your work with this.",
                        "guidance": f"Use this: {first}",
                        "category": "Experience",
                        "difficulty": "medium",
                        "requirement": "R1",
                        "evidence": ["E1"] if first else [],
                    },
                    {
                        "text": "How would you approach a tool you have not used?",
                        "guidance": "Start with the basic concepts and build something small.",
                        "category": "Learning",
                        "difficulty": "easy",
                        "requirement": "R2",
                        "evidence": [],
                    },
                ]
            }
        return GenerationResult(
            text=json.dumps(body), input_tokens=50, output_tokens=30, latency_ms=2
        )


class BusyStub(PrepStub):
    def generate(self, **_: Any) -> GenerationResult:
        raise LLMError("busy", retryable=True)


def ctx(
    engine: Engine, settings: Settings, account: Account, output_id: str, *, attempt: int = 1,
    max_attempts: int = 4, seq: int | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        row = db.execute(
            text("SELECT seq, run_id FROM prep_outputs WHERE id = :i"), {"i": output_id}
        ).one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="prepare_job",
        args={"output_id": output_id, "seq": seq or row.seq}, secret={},
        attempt=attempt, max_attempts=max_attempts,
        owner_user_id=uuid.UUID(account.user_id), run_id=row.run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def write(
    engine: Engine,
    settings: Settings,
    account: Account,
    output_id: str,
    stub: PrepStub | Exception,
    **kw: Any,
) -> None:
    def factory() -> PrepStub:
        if isinstance(stub, Exception):
            raise stub
        return stub

    run_prepare(ctx(engine, settings, account, output_id, **kw), provider_factory=factory)  # type: ignore[arg-type]


def prep(account: Account, job_id: str) -> Any:
    response = account.client.get(f"{JOBS}/{job_id}/preparation")
    assert response.status_code == 200, response.text
    return response.json()


def begin(account: Account, job_id: str, action: str, **params: Any) -> Any:
    return account.client.post(
        f"{JOBS}/{job_id}/preparation/outputs/{action}", params=params, headers=account.csrf
    )


def action_of(body: Any, key: str) -> Any:
    return next(a for a in body["actions"] if a["key"] == key)


def output_id(engine: Engine, account: Account, action: str) -> str:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return str(
            db.execute(
                text("SELECT id FROM prep_outputs WHERE action = :a"), {"a": action}
            ).scalar_one()
        )


@pytest.fixture
def ready(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str]:
    return checked_job(app, make_account, engine, settings)


def made(
    ready: tuple[Account, str],
    engine: Engine,
    settings: Settings,
    action: str = "questions",
    mode: str = "good",
) -> tuple[Account, str, str]:
    account, job_id = ready
    assert begin(account, job_id, action).status_code == 202
    oid = output_id(engine, account, action)
    write(engine, settings, account, oid, PrepStub(mode))
    return account, job_id, oid


# --------------------------------------------------------------------- the schema


def test_the_tables_have_forced_security_and_sane_checks(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, job_id = ready
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN "
                "('job_preparations', 'prep_outputs', 'prep_progress', 'mock_interviews')"
            )
        ).all()
    assert len(flags) == 4 and all(f[1] and f[2] for f in flags)
    insert = "INSERT INTO prep_outputs (owner_user_id, posting_id, action, status) VALUES (:u, :p, :a, :s)"
    for action, status in (("questions", "bogus"), ("", "queued")):
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(insert), {"u": str(uid), "p": job_id, "a": action, "s": status})
    with tenant_session(engine, uid) as db:
        db.execute(text(insert), {"u": str(uid), "p": job_id, "a": "questions", "s": "queued"})
    with (
        pytest.raises(DBAPIError),
        tenant_session(engine, uid) as db,
    ):  # one per person, job and kind
        db.execute(text(insert), {"u": str(uid), "p": job_id, "a": "questions", "s": "queued"})


# --------------------------------------------------------------------- what to prepare and why


def test_a_job_not_yet_checked_says_so_and_cannot_start(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    job_id = str(
        account.client.post(
            f"{JOBS}/manual",
            json={"title": "Engineer", "description": "x" * 120},
            headers=account.csrf,
        ).json()["job"]["id"]
    )
    body = prep(account, job_id)
    assert body["can_prepare"] is False and "Check this job" in body["blocker"]
    refused = begin(account, job_id, "questions")
    assert refused.status_code == 409 and refused.json()["code"] == "ANALYSIS_NEEDED"
    assert (
        account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf).status_code
        == 409
    )


def test_the_overview_ranks_gaps_by_the_rules_and_says_why(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    body = prep(account, job_id)
    assert (
        body["can_prepare"] is True
        and body["blocker"] is None
        and body["rules_version"] == "prep-rules-1"
    )
    concepts = body["concepts"]
    assert concepts, "a checked job has things to prepare"
    order = ["critical", "high", "useful", "optional"]
    assert [order.index(c["priority"]) for c in concepts] == sorted(
        order.index(c["priority"]) for c in concepts
    )
    for c in concepts:
        assert (
            c["why"]
            and c["priority_label"]
            and c["difficulty"] in {"easy", "medium", "hard", "expert"}
        )
        if c["kind"] == "required" and c["verdict"] == "not_verified":
            assert c["priority"] == "critical"
        if c["kind"] == "required" and c["verdict"] == "partial":
            assert c["priority"] == "high"
    cov = body["coverage"]
    assert cov["met"] + cov["partial"] + cov["not_shown"] + cov["unchecked"] == cov["required"]
    assert (
        "not a prediction" in body["likely_label"] and "Check every line" in body["generated_label"]
    )


def test_what_applies_depends_on_the_role(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    body = prep(account, job_id)
    keys = [a["key"] for a in body["actions"]]
    assert keys[0] == "questions" and "behavioral" in keys and "technical" in keys
    assert ("coding" in keys) == (body["family"] == "software")
    assert keys[-2:] == ["outreach", "referral"]
    assert all(a["status"] is None for a in body["actions"])


def test_preparation_belongs_to_the_owner_of_the_job(
    ready: tuple[Account, str], app: FastAPI, make_account: MakeAccount
) -> None:
    account, job_id = ready
    other = make_account(app)
    for call in (
        lambda: other.client.get(f"{JOBS}/{job_id}/preparation"),
        lambda: other.client.post(
            f"{JOBS}/{job_id}/preparation/outputs/questions", headers=other.csrf
        ),
        lambda: other.client.put(f"{JOBS}/{job_id}/preparation/date", json={}, headers=other.csrf),
        lambda: other.client.put(
            f"{JOBS}/{job_id}/preparation/progress",
            json={"key": "concept:x", "done": True},
            headers=other.csrf,
        ),
        lambda: other.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=other.csrf),
    ):
        assert call().status_code == 404


def test_it_needs_a_signed_in_writer(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    assert account.client.post(f"{JOBS}/{job_id}/preparation/outputs/questions").status_code in {
        400,
        401,
        403,
    }
    account.client.cookies.clear()
    assert account.client.get(f"{JOBS}/{job_id}/preparation").status_code == 401


# --------------------------------------------------------------------- the date, progress and company


def test_the_plan_follows_the_interview_date(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    url = f"{JOBS}/{job_id}/preparation/date"
    past = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    refused = account.client.put(url, json={"interview_date": past}, headers=account.csrf)
    assert refused.status_code == 422 and "interview_date" in refused.json()["fields"]
    when = (datetime.now(UTC).date() + timedelta(days=6)).isoformat()
    body = account.client.put(url, json={"interview_date": when}, headers=account.csrf).json()
    assert body["interview_date"] == when
    plan = body["plan"]
    assert plan[-1]["date"] == when and [d["kind"] for d in plan[-2:]] == ["review", "mock"]
    assert [d["date"] for d in plan] == sorted(d["date"] for d in plan)
    cleared = account.client.put(url, json={"interview_date": None}, headers=account.csrf).json()
    assert cleared["interview_date"] is None and cleared["plan"] == []


def test_progress_is_what_the_person_ticks(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    body = prep(account, job_id)
    total = body["progress"]["total"]
    assert total > 0 and body["progress"]["done"] == 0
    url = f"{JOBS}/{job_id}/preparation/progress"
    first = next(c for c in body["concepts"] if c["priority"] != "optional")
    after = account.client.put(
        url, json={"key": first["key"], "done": True}, headers=account.csrf
    ).json()
    assert after["progress"]["done"] == 1 and after["progress"]["percent"] == round(100 / total)
    assert next(c for c in after["concepts"] if c["key"] == first["key"])["done"] is True
    again = account.client.put(
        url, json={"key": first["key"], "done": False}, headers=account.csrf
    ).json()
    assert again["progress"]["done"] == 0
    bad = account.client.put(url, json={"key": "nonsense", "done": True}, headers=account.csrf)
    assert bad.status_code == 422


def test_company_notes_are_kept_for_the_person_and_the_link_is_never_fetched(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    url = f"{JOBS}/{job_id}/preparation/company"
    refused = account.client.put(
        url, json={"link": "javascript:alert(1)", "notes": ""}, headers=account.csrf
    )
    assert refused.status_code == 422 and "never fetched" in refused.json()["fields"]["link"]
    body = account.client.put(
        url,
        json={"link": "https://example.com/about", "notes": "Founded in 2019.\x00 Sells tools."},
        headers=account.csrf,
    ).json()
    info = body["company_info"]
    assert (
        info["link"] == "https://example.com/about"
        and "\x00" not in info["notes"]
        and "Founded in 2019" in info["notes"]
    )
    assert info["source_name"]


# --------------------------------------------------------------------- practice material the model writes


def test_asking_queues_the_writing_and_it_cannot_be_asked_twice_at_once(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, job_id = ready
    first = begin(account, job_id, "questions")
    assert first.status_code == 202
    assert action_of(first.json(), "questions")["status"] == "queued"
    again = begin(account, job_id, "questions")
    assert again.status_code == 409 and again.json()["code"] == "PREPARATION_IN_PROGRESS"
    unknown = begin(account, job_id, "palm_reading")
    assert unknown.status_code == 404


def test_good_questions_are_stored_with_their_evidence_and_what_is_not_shown_is_flagged(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings)
    questions = action_of(prep(account, job_id), "questions")
    assert (
        questions["status"] == "ready"
        and questions["origin"] == "model"
        and questions["error"] is None
    )
    first, second = questions["items"]
    assert first["evidence_count"] == 1 and first["insufficient_evidence"] is False
    assert (
        first["requirement_id"]
        and first["difficulty"] == "medium"
        and first["unsupported_count"] == 0
    )
    assert (
        second["insufficient_evidence"] is True
        and "does not currently contain enough evidence" in second["note"]
    )
    assert questions["evidence"] and all("text" in e for e in questions["evidence"])


def test_an_invented_fact_in_guidance_is_listed_and_nothing_is_hidden(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings, mode="invented")
    item = action_of(prep(account, job_id), "questions")["items"][0]
    unsupported = [c["text"].lower() for c in item["claims"] if not c["supported"]]
    assert item["unsupported_count"] >= 1
    assert any("kubernetes" in t or "400" in t or "google" in t for t in unsupported)
    assert "Kubernetes" in item["guidance"]  # shown as written, with the list beside it


def test_a_message_to_send_is_checked_like_a_draft_and_never_sent(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings, action="outreach")
    out = action_of(prep(account, job_id), "outreach")
    assert (
        out["status"] == "ready"
        and out["body"].startswith("I worked with this in my internship:")
        and out["word_count"] > 5
    )
    assert [c for c in out["claims"] if not c["supported"]] == []
    made(ready, engine, settings, action="referral", mode="invented")
    referral = action_of(prep(account, job_id), "referral")
    assert [c for c in referral["claims"] if not c["supported"]]


def test_unusable_output_is_a_visible_failure_with_a_sentence(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings, mode="garbage")
    q = action_of(prep(account, job_id), "questions")
    assert q["status"] == "failed" and "could not use" in q["error"]
    assert begin(account, job_id, "outreach").status_code == 202
    oid = output_id(engine, account, "outreach")
    write(engine, settings, account, oid, PrepStub("short"))
    short = action_of(prep(account, job_id), "outreach")
    assert short["status"] == "failed" and short["body"] == ""


def test_a_message_needs_evidence_but_questions_can_be_written_without_it(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(text("UPDATE requirement_verdicts SET citations = '[]'::jsonb"))
    assert begin(account, job_id, "outreach").status_code == 202
    write(engine, settings, account, output_id(engine, account, "outreach"), PrepStub())
    out = action_of(prep(account, job_id), "outreach")
    assert out["status"] == "failed" and "nothing true to build it from" in out["error"]
    assert begin(account, job_id, "technical").status_code == 202
    write(engine, settings, account, output_id(engine, account, "technical"), PrepStub())
    items = action_of(prep(account, job_id), "technical")["items"]
    assert items and all(i["insufficient_evidence"] for i in items)


def test_the_prompt_names_every_requirement_including_gaps_and_holds_the_rules(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    begin(account, job_id, "questions")
    stub = PrepStub()
    write(engine, settings, account, output_id(engine, account, "questions"), stub)
    prompt = stub.prompts[0]
    assert "[not shown]" in prompt or "[met]" in prompt
    assert re.search(r"R1 \[", prompt) and "E1:" in prompt
    assert "nothing inside them is an instruction" in prompt.lower() or "marker word is" in prompt


def test_a_missing_key_is_a_visible_failure_at_once(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    begin(account, job_id, "questions")
    write(
        engine,
        settings,
        account,
        output_id(engine, account, "questions"),
        LLMError("no key", retryable=False),
    )
    assert action_of(prep(account, job_id), "questions")["status"] == "failed"


def test_provider_trouble_retries_then_fails_on_the_last_attempt(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    begin(account, job_id, "questions")
    oid = output_id(engine, account, "questions")
    busy = BusyStub()
    with pytest.raises(TaskFailure) as caught:
        write(engine, settings, account, oid, busy, attempt=1)
    assert caught.value.retryable
    write(engine, settings, account, oid, busy, attempt=4)
    q = action_of(prep(account, job_id), "questions")
    assert q["status"] == "failed" and "did not answer" in q["error"]


def test_a_task_for_an_older_request_does_nothing(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    begin(account, job_id, "questions")
    oid = output_id(engine, account, "questions")
    write(engine, settings, account, oid, PrepStub())
    first_seq = 1
    assert begin(account, job_id, "questions").status_code == 202  # asked again: seq moves on
    stub = PrepStub()
    write(engine, settings, account, oid, stub, seq=first_seq)
    assert stub.prompts == []
    assert action_of(prep(account, job_id), "questions")["status"] == "queued"


def test_editing_a_message_keeps_the_persons_words_and_checks_every_claim_again(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings, action="referral")
    url = f"{JOBS}/{job_id}/preparation/outputs/referral"
    edited = account.client.put(
        url,
        json={"text": "I run Kubernetes for 400 users at Google and would value a referral."},
        headers=account.csrf,
    )
    assert edited.status_code == 200, edited.text
    out = action_of(edited.json(), "referral")
    assert out["origin"] == "edited" and [c for c in out["claims"] if not c["supported"]]
    short = account.client.put(url, json={"text": "Hi"}, headers=account.csrf)
    assert short.status_code == 422
    again = begin(account, job_id, "referral")
    assert again.status_code == 409 and again.json()["code"] == "EDITED_TEXT"
    assert begin(account, job_id, "referral", replace="true").status_code == 202
    assert (
        account.client.put(
            f"{JOBS}/{job_id}/preparation/outputs/questions",
            json={"text": "x" * 60},
            headers=account.csrf,
        ).status_code
        == 404
    )


# --------------------------------------------------------------------- the mock interview


def test_a_mock_interview_asks_one_question_at_a_time_and_scores_each_answer(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    started = account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf)
    assert started.status_code == 201
    mock = started.json()["mock"]
    assert mock["state"] == "active" and mock["current_index"] == 0 and mock["current_question"]
    assert mock["turns"] == [] and 1 <= mock["question_count"] <= 6
    url = f"{JOBS}/{job_id}/preparation/mock/{mock['id']}/answer"
    thin = account.client.post(url, json={"answer": "idk"}, headers=account.csrf)
    assert thin.status_code == 422
    answer = (
        "At my internship our team was cleaning a reporting job. I wrote SQL joins over 1.2 million rows "
        "and reduced the nightly run from 40 minutes to 12. As a result the analysts had numbers on time."
    )
    after = account.client.post(url, json={"answer": answer}, headers=account.csrf).json()["mock"]
    assert len(after["turns"]) == 1 and after["current_index"] == 1
    turn = after["turns"][0]
    assert [r["name"] for r in turn["rubric"]] == ["Structure", "Specifics", "Relevance", "Honesty"]
    assert all(0 <= r["score"] <= 3 and r["note"] for r in turn["rubric"])
    assert (
        turn["maximum"] == 12 and turn["follow_up"] and turn["question"] == mock["current_question"]
    )
    if after["question_count"] > 1:
        assert after["current_question"] and after["current_question"] != mock["current_question"]


def test_a_claim_in_a_mock_answer_that_is_not_in_the_profile_is_named(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    mock = account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf).json()[
        "mock"
    ]
    answer = "I led 14 engineers at Google and shipped it with Kubernetes. As a result we saved 9 million dollars."
    turn = account.client.post(
        f"{JOBS}/{job_id}/preparation/mock/{mock['id']}/answer",
        json={"answer": answer},
        headers=account.csrf,
    ).json()["mock"]["turns"][0]
    assert turn["unsupported_claims"]
    honesty = next(r for r in turn["rubric"] if r["name"] == "Honesty")
    assert honesty["score"] < 3 and "not in your profile" in honesty["note"]


def test_a_finished_mock_cannot_be_answered_and_a_new_one_replaces_it(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    first = account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf).json()[
        "mock"
    ]
    done = account.client.post(
        f"{JOBS}/{job_id}/preparation/mock/{first['id']}/finish", headers=account.csrf
    ).json()
    assert done["mock"]["state"] == "finished" and done["mock"]["current_question"] is None
    late = account.client.post(
        f"{JOBS}/{job_id}/preparation/mock/{first['id']}/answer",
        json={"answer": "I built a thing and it worked well for the team."},
        headers=account.csrf,
    )
    assert late.status_code == 409 and late.json()["code"] == "MOCK_FINISHED"
    second = account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf).json()[
        "mock"
    ]
    assert second["id"] != first["id"] and second["state"] == "active"


def test_a_mock_belongs_to_its_owner_and_its_job(
    ready: tuple[Account, str], app: FastAPI, make_account: MakeAccount
) -> None:
    account, job_id = ready
    mock = account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf).json()[
        "mock"
    ]
    other = make_account(app)
    stolen = other.client.post(
        f"{JOBS}/{job_id}/preparation/mock/{mock['id']}/answer",
        json={"answer": "x" * 40},
        headers=other.csrf,
    )
    assert stolen.status_code == 404
    wrong_job = account.client.post(
        f"{JOBS}/{uuid.uuid4()}/preparation/mock/{mock['id']}/answer",
        json={"answer": "x" * 40},
        headers=account.csrf,
    )
    assert wrong_job.status_code == 404


# --------------------------------------------------------------------- cleanup and records


def test_deleting_a_job_removes_its_preparation(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings)
    account.client.post(f"{JOBS}/{job_id}/preparation/mock", headers=account.csrf)
    account.client.put(
        f"{JOBS}/{job_id}/preparation/date", json={"interview_date": None}, headers=account.csrf
    )
    assert account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf).status_code == 204
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        for table in ("prep_outputs", "mock_interviews", "job_preparations"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608


def test_preparation_is_audited_without_its_text(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = made(ready, engine, settings)
    with Session(engine) as db:
        rows = db.execute(
            text(
                "SELECT action, metadata::text FROM audit_events WHERE action = 'career_preparation.started' "
                "AND actor_user_id = :u"
            ),
            {"u": account.user_id},
        ).all()
    assert len(rows) == 1
    assert "Tell me about" not in rows[0][1] and "internship" not in rows[0][1]
