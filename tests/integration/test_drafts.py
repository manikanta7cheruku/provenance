"""Checkpoint 2.10: application drafts. The model writes, code checks every claim, the person edits."""

import json
import re
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
from test_tailoring import checked_job

from pv_config import Settings
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.draft_application import run_draft

JOBS = "/api/v1/jobs"
MakeAccount = Callable[..., Account]
QUESTION = "Why do you want this role?"


class DraftStub:
    """Stands in for the model. `mode` says what it writes from the first piece of evidence it sees."""

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
        if self.mode == "good":
            body: dict[str, Any] = {
                "text": f"I worked with this in my internship: {first}",
                "evidence": ["E1"],
            }
        elif self.mode == "invented":
            body = {
                "text": f"I worked with this: {first} I also run Kubernetes clusters for 400 users at Google.",
                "evidence": ["E1", "E99"],
            }
        elif self.mode == "short":
            body = {"text": "Too short.", "evidence": []}
        elif self.mode == "garbage":
            return GenerationResult(
                text="not json at all", input_tokens=5, output_tokens=5, latency_ms=1
            )
        else:
            body = {"text": "x", "evidence": []}
        return GenerationResult(
            text=json.dumps(body), input_tokens=50, output_tokens=30, latency_ms=2
        )


def ctx(
    engine: Engine, settings: Settings, account: Account, draft_id: str, *, attempt: int = 1,
    max_attempts: int = 4, seq: int | None = None, owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        row = db.execute(
            text("SELECT seq, run_id FROM application_drafts WHERE id = :i"), {"i": draft_id}
        ).one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="draft_application",
        args={"draft_id": draft_id, "seq": seq or row.seq}, secret={},
        attempt=attempt, max_attempts=max_attempts,
        owner_user_id=uuid.UUID(owner or account.user_id), run_id=row.run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def write(
    engine: Engine,
    settings: Settings,
    account: Account,
    draft_id: str,
    stub: DraftStub | Exception,
    **kw: Any,
) -> None:
    def factory() -> DraftStub:
        if isinstance(stub, Exception):
            raise stub
        return stub

    run_draft(ctx(engine, settings, account, draft_id, **kw), provider_factory=factory)  # type: ignore[arg-type]


def begin(
    account: Account, job_id: str, kind: str = "cover_note", question: str = "", **extra: Any
) -> Any:
    return account.client.post(
        f"{JOBS}/{job_id}/drafts",
        json={"kind": kind, "question": question, **extra},
        headers=account.csrf,
    )


def shown(account: Account, job_id: str) -> Any:
    response = account.client.get(f"{JOBS}/{job_id}/drafts")
    assert response.status_code == 200, response.text
    return response.json()


def draft_id_of(body: Any, kind: str = "cover_note") -> str:
    return str(next(d["id"] for d in body["drafts"] if d["kind"] == kind))


@pytest.fixture
def ready(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str]:
    return checked_job(app, make_account, engine, settings)


def written(
    ready: tuple[Account, str], engine: Engine, settings: Settings, mode: str = "good"
) -> tuple[Account, str, str]:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())
    write(engine, settings, account, draft_id, DraftStub(mode))
    return account, job_id, draft_id


# --------------------------------------------------------------------- the schema


def test_the_tables_have_forced_security_and_sane_checks(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, job_id = ready
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = {
            r.relname: (r.relrowsecurity, r.relforcerowsecurity)
            for r in db.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN "
                    "('application_drafts', 'shortlist_settings', 'shortlist_runs', 'shortlist_items')"
                )
            )
        }
    assert set(flags.values()) == {(True, True)} and len(flags) == 4
    bad = {
        "an unknown kind": "INSERT INTO application_drafts (owner_user_id, posting_id, kind) VALUES (:u, :p, 'letter')",
        "an unknown state": "INSERT INTO application_drafts (owner_user_id, posting_id, kind, status) VALUES (:u, :p, 'cover_note', 'sent')",
        "a cover note with a question": "INSERT INTO application_drafts (owner_user_id, posting_id, kind, question, question_key) VALUES (:u, :p, 'cover_note', 'Why?', 'why')",
        "an answer with no question": "INSERT INTO application_drafts (owner_user_id, posting_id, kind) VALUES (:u, :p, 'answer')",
        "a body that is too long": "INSERT INTO application_drafts (owner_user_id, posting_id, kind, body) VALUES (:u, :p, 'cover_note', repeat('x', 6001))",
        "a seq of zero": "INSERT INTO application_drafts (owner_user_id, posting_id, kind, seq) VALUES (:u, :p, 'cover_note', 0)",
        "an hour of 24": "INSERT INTO shortlist_settings (owner_user_id, hour) VALUES (:u, 24)",
        "enabled with no next time": "INSERT INTO shortlist_settings (owner_user_id, enabled) VALUES (:u, true)",
        "more than ten jobs": "INSERT INTO shortlist_settings (owner_user_id, max_items) VALUES (:u, 11)",
        "an unknown outcome": "INSERT INTO shortlist_runs (owner_user_id, slot, outcome) VALUES (:u, now(), 'maybe')",
    }  # fmt: skip
    for name, sql in bad.items():
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(sql), {"u": str(uid), "p": job_id})
        assert name
    with tenant_session(engine, uid) as db:
        db.execute(
            text(
                "INSERT INTO shortlist_runs (owner_user_id, slot, outcome) VALUES (:u, '2026-11-02T08:00:00Z', 'nothing')"
            ),
            {"u": str(uid)},
        )
    with (
        pytest.raises(DBAPIError),
        tenant_session(engine, uid) as db,
    ):  # one run per person and time
        db.execute(
            text(
                "INSERT INTO shortlist_runs (owner_user_id, slot, outcome) VALUES (:u, '2026-11-02T08:00:00Z', 'sent')"
            ),
            {"u": str(uid)},
        )


# --------------------------------------------------------------------- asking


def test_a_draft_needs_the_job_to_be_checked_first(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    job_id = str(
        account.client.post(
            f"{JOBS}/manual",
            json={"title": "Engineer", "description": "x" * 120},
            headers=account.csrf,
        ).json()["job"]["id"]
    )
    body = shown(account, job_id)
    assert (
        body["can_write"] is False and "Check this job" in body["blocker"] and body["drafts"] == []
    )
    refused = begin(account, job_id)
    assert refused.status_code == 409 and refused.json()["code"] == "ANALYSIS_NEEDED"


def test_what_is_on_offer_is_labelled_a_draft_and_lists_the_common_questions(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    body = shown(account, job_id)
    assert body["can_write"] is True and body["blocker"] is None and body["drafts"] == []
    assert "Draft" in body["label"] and "Nothing is sent anywhere" in body["label"]
    assert [q["key"] for q in body["questions"]][:2] == ["why_role", "why_company"] and body[
        "max_drafts"
    ] == 8


def test_asking_queues_the_writing_and_shows_it_as_working(
    ready: tuple[Account, str], engine: Engine
) -> None:
    account, job_id = ready
    response = begin(account, job_id)
    assert response.status_code == 202, response.text
    (draft,) = response.json()["drafts"]
    assert (draft["kind"], draft["ui_state"], draft["body"]) == ("cover_note", "working", "")
    with Session(engine) as db:
        queued = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'draft_application' AND owner_user_id = :u AND state = 'queued'"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert queued == 1


def test_an_answer_needs_a_real_question(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    for question in ("", "   ", "Why?"):
        response = begin(account, job_id, "answer", question)
        assert response.status_code == 422 and "question" in response.json()["fields"], question


def test_the_same_question_in_other_words_of_case_is_the_same_draft(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    first = draft_id_of(begin(account, job_id, "answer", QUESTION).json(), "answer")
    write(engine, settings, account, first, DraftStub())
    again = begin(account, job_id, "answer", "  WHY do you want this ROLE  ").json()
    assert len(again["drafts"]) == 1 and again["drafts"][0]["id"] == first


def test_a_draft_that_is_being_written_cannot_be_asked_for_again(
    ready: tuple[Account, str],
) -> None:
    account, job_id = ready
    begin(account, job_id)
    again = begin(account, job_id)
    assert again.status_code == 409 and again.json()["code"] == "DRAFT_IN_PROGRESS"


def test_one_job_keeps_at_most_eight_drafts(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    begin(account, job_id)
    for n in range(7):
        assert (
            begin(account, job_id, "answer", f"Question number {n} about this role?").status_code
            == 202
        )
    over = begin(account, job_id, "answer", "One question too many for this role?")
    assert over.status_code == 409 and over.json()["code"] == "TOO_MANY_DRAFTS"
    assert len(shown(account, job_id)["drafts"]) == 8


# --------------------------------------------------------------------- the worker


def test_a_good_draft_is_stored_with_its_evidence_and_nothing_unsupported(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    (draft,) = shown(account, job_id)["drafts"]
    assert (
        draft["ui_state"] == "ready"
        and draft["origin"] == "model"
        and draft["error_message"] is None
    )
    assert (
        draft["body"].startswith("I worked with this in my internship:") and draft["word_count"] > 5
    )
    assert draft["unsupported_count"] == 0 and all(c["supported"] for c in draft["claims"])
    assert draft["evidence"] and any(e["cited"] for e in draft["evidence"])
    assert draft["id"] == draft_id


def test_an_invented_fact_is_listed_for_the_person_and_nothing_is_hidden(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, _ = written(ready, engine, settings, "invented")
    (draft,) = shown(account, job_id)["drafts"]
    assert (
        draft["ui_state"] == "ready" and "Kubernetes" in draft["body"]
    )  # the text is kept as written
    flagged = {c["text"] for c in draft["claims"] if not c["supported"]}
    assert {"kubernetes", "400", "google"} <= flagged
    assert draft["unsupported_count"] == len(flagged)


def test_an_answer_that_is_too_short_or_not_json_is_a_visible_failure(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    for mode in ("short", "garbage"):
        account, job_id = ready
        draft_id = draft_id_of(
            begin(account, job_id, "answer", f"A question about {mode} answers here?").json(),
            "answer",
        )
        write(engine, settings, account, draft_id, DraftStub(mode))
        draft = next(d for d in shown(account, job_id)["drafts"] if d["id"] == draft_id)
        assert draft["ui_state"] == "failed" and "could not use" in draft["error_message"], mode


def test_a_job_with_nothing_supported_has_nothing_true_to_write_from(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(text("UPDATE requirement_verdicts SET verdict = 'not_verified'"))
    draft_id = draft_id_of(begin(account, job_id).json())
    stub = DraftStub()
    write(engine, settings, account, draft_id, stub)
    draft = shown(account, job_id)["drafts"][0]
    assert draft["ui_state"] == "failed" and "nothing true" in draft["error_message"]
    assert stub.prompts == []  # the model was never asked


def test_the_prompt_holds_the_supported_evidence_and_names_what_not_to_claim(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())
    stub = DraftStub()
    write(engine, settings, account, draft_id, stub)
    (prompt,) = stub.prompts
    assert "Cleaned six CSV sources" in prompt and "unsupported_requirements_do_not_claim" in prompt
    assert "Write a cover note for this job." in prompt


def test_a_missing_key_is_a_visible_failure_at_once(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())
    write(engine, settings, account, draft_id, LLMError("no key", retryable=False))
    draft = shown(account, job_id)["drafts"][0]
    assert draft["ui_state"] == "failed" and "not set up" in draft["error_message"]


def test_provider_trouble_retries_then_fails_on_the_last_attempt(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())

    class Busy(DraftStub):
        def generate(self, **kw: Any) -> GenerationResult:
            raise LLMError("busy", retryable=True)

    with pytest.raises(TaskFailure):
        write(engine, settings, account, draft_id, Busy(), attempt=1)
    assert shown(account, job_id)["drafts"][0]["ui_state"] == "working"
    write(engine, settings, account, draft_id, Busy(), attempt=4)
    draft = shown(account, job_id)["drafts"][0]
    assert draft["ui_state"] == "failed" and "did not answer" in draft["error_message"]


def test_a_task_for_an_older_request_or_a_deleted_draft_does_nothing(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    stub = DraftStub()
    c = ctx(engine, settings, account, draft_id)
    begin(account, job_id, replace=True)  # asked again: the seq moves on
    run_draft(
        TaskContext(**{**c.__dict__, "args": {"draft_id": draft_id, "seq": 1}}),
        provider_factory=lambda: stub,
    )  # type: ignore[arg-type]
    assert stub.prompts == []
    assert (
        account.client.delete(
            f"{JOBS}/{job_id}/drafts/{draft_id}", headers=account.csrf
        ).status_code
        == 204
    )
    run_draft(c, provider_factory=lambda: stub)  # type: ignore[arg-type]
    assert stub.prompts == [] and shown(account, job_id)["drafts"] == []


# --------------------------------------------------------------------- editing


def test_editing_keeps_the_persons_words_and_checks_every_claim_again(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    url = f"{JOBS}/{job_id}/drafts/{draft_id}"
    added = account.client.put(
        url,
        json={"body": "I cleaned six CSV sources with pandas. I also built Kubernetes clusters."},
        headers=account.csrf,
    )
    assert added.status_code == 200, added.text
    draft = added.json()
    assert draft["origin"] == "edited" and draft["body"].endswith("clusters.")
    assert {c["text"] for c in draft["claims"] if not c["supported"]} == {"kubernetes"}
    removed = account.client.put(
        url, json={"body": "I cleaned six CSV sources with pandas."}, headers=account.csrf
    ).json()
    assert removed["unsupported_count"] == 0 and removed["origin"] == "edited"
    assert shown(account, job_id)["drafts"][0]["body"] == "I cleaned six CSV sources with pandas."


def test_a_draft_edit_is_tidied_and_limited(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    url = f"{JOBS}/{job_id}/drafts/{draft_id}"
    tidy = account.client.put(
        url, json={"body": "  One\x00  paragraph.\r\n\r\n\r\nTwo.  "}, headers=account.csrf
    ).json()
    assert tidy["body"] == "One paragraph.\n\nTwo."
    for body in ("   ", "x" * 6001):
        refused = account.client.put(url, json={"body": body}, headers=account.csrf)
        assert refused.status_code == 422 and "body" in refused.json()["fields"], len(body)
    assert (
        account.client.put(url, json={"body": "ok", "extra": 1}, headers=account.csrf).status_code
        == 422
    )


def test_a_draft_still_being_written_cannot_be_edited(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())
    refused = account.client.put(
        f"{JOBS}/{job_id}/drafts/{draft_id}", json={"body": "Mine."}, headers=account.csrf
    )
    assert refused.status_code == 409 and refused.json()["code"] == "DRAFT_IN_PROGRESS"


def test_writing_again_does_not_throw_away_edits_unless_asked(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    account.client.put(
        f"{JOBS}/{job_id}/drafts/{draft_id}",
        json={"body": "My own careful words about this role."},
        headers=account.csrf,
    )
    refused = begin(account, job_id)
    assert refused.status_code == 409 and refused.json()["code"] == "EDITED_DRAFT"
    assert shown(account, job_id)["drafts"][0]["body"] == "My own careful words about this role."
    assert begin(account, job_id, replace=True).status_code == 202
    assert (
        shown(account, job_id)["drafts"][0]["body"] == "My own careful words about this role."
    )  # kept until the new one is ready
    write(engine, settings, account, draft_id, DraftStub())
    fresh = shown(account, job_id)["drafts"][0]
    assert fresh["origin"] == "model" and fresh["body"].startswith("I worked with this")


def test_a_failed_draft_can_be_written_again_without_asking(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    draft_id = draft_id_of(begin(account, job_id).json())
    write(engine, settings, account, draft_id, LLMError("no key", retryable=False))
    assert begin(account, job_id).status_code == 202


# --------------------------------------------------------------------- privacy


def test_drafts_belong_to_their_owner(
    app: FastAPI,
    make_account: MakeAccount,
    ready: tuple[Account, str],
    engine: Engine,
    settings: Settings,
) -> None:
    owner, job_id, draft_id = written(ready, engine, settings)
    other = make_account(app)
    assert other.client.get(f"{JOBS}/{job_id}/drafts").status_code == 404
    assert begin(other, job_id).status_code == 404
    assert (
        other.client.put(
            f"{JOBS}/{job_id}/drafts/{draft_id}", json={"body": "mine now"}, headers=other.csrf
        ).status_code
        == 404
    )
    assert (
        other.client.delete(f"{JOBS}/{job_id}/drafts/{draft_id}", headers=other.csrf).status_code
        == 404
    )
    with tenant_session(engine, uuid.UUID(other.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM application_drafts")).scalar_one() == 0
    assert shown(owner, job_id)["drafts"][0]["id"] == draft_id


def test_a_draft_is_not_reachable_through_another_job(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    other_job = str(
        account.client.post(
            f"{JOBS}/manual",
            json={"title": "Other", "description": "y" * 120},
            headers=account.csrf,
        ).json()["job"]["id"]
    )
    assert (
        account.client.put(
            f"{JOBS}/{other_job}/drafts/{draft_id}", json={"body": "x y z"}, headers=account.csrf
        ).status_code
        == 404
    )


def test_deleting_a_job_removes_its_drafts_and_deleting_a_draft_removes_only_it(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    begin(account, job_id, "answer", QUESTION)
    assert (
        account.client.delete(
            f"{JOBS}/{job_id}/drafts/{draft_id}", headers=account.csrf
        ).status_code
        == 204
    )
    assert [d["kind"] for d in shown(account, job_id)["drafts"]] == ["answer"]
    assert account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf).status_code == 204
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        assert db.execute(text("SELECT count(*) FROM application_drafts")).scalar_one() == 0


def test_drafts_need_a_signed_in_writer(ready: tuple[Account, str]) -> None:
    account, job_id = ready
    assert account.client.post(
        f"{JOBS}/{job_id}/drafts", json={"kind": "cover_note"}
    ).status_code in (401, 403)
    account.client.cookies.clear()
    assert begin(account, job_id).status_code == 401
    assert account.client.get(f"{JOBS}/{job_id}/drafts").status_code == 401


def test_drafts_are_audited_without_their_text(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id, draft_id = written(ready, engine, settings)
    account.client.put(
        f"{JOBS}/{job_id}/drafts/{draft_id}",
        json={"body": "A very private sentence about my plans."},
        headers=account.csrf,
    )
    account.client.delete(f"{JOBS}/{job_id}/drafts/{draft_id}", headers=account.csrf)
    with Session(engine) as db:
        rows = list(
            db.execute(
                text(
                    "SELECT action, metadata FROM audit_events WHERE actor_user_id = :u AND action LIKE 'application_draft.%' ORDER BY created_at"
                ),
                {"u": account.user_id},
            )
        )
    assert [r.action for r in rows] == [
        "application_draft.started",
        "application_draft.edited",
        "application_draft.deleted",
    ]
    assert "private sentence" not in json.dumps([r.metadata for r in rows])
