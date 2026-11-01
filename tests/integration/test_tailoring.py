"""Checkpoint 2.4: tailoring a resume to a job. The model proposes, code verifies, the person decides."""

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
from test_analysis import FULL_PLAN, AgentStub, add_profile, read_job, start
from test_analysis import run as run_analysis
from test_studio import make_doc, save

from pv_config import Settings
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.tailor_resume import run_tailor

STUDIO = "/api/v1/studio"
MakeAccount = Callable[..., Account]

CLEANED = "Cleaned six CSV sources with pandas and ran hypothesis tests on churn"
OTHER = "Built weekly reports for managers"


class TailorStub:
    """Stands in for the model. `mode` says what it proposes for the part that holds CLEANED."""

    name = "stub"

    def __init__(self, mode: str = "good") -> None:
        self.mode = mode
        self.prompts: list[str] = []

    def list_models(self) -> list[Any]:
        return []

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError

    @staticmethod
    def _label(prompt: str, pattern: str, snippet: str) -> str | None:
        for line in prompt.splitlines():
            found = re.match(pattern, line)
            if found and snippet in prompt.split(found.group(0), 1)[1].split("\n\n", 1)[0]:
                return found.group(1)
        return None

    def generate(self, *, prompt: str, **_: Any) -> GenerationResult:
        self.prompts.append(prompt)
        if self.mode == "fail":
            raise LLMError("busy", retryable=True)
        part = self._label(prompt, r"^(P\d+) \(", "Cleaned six CSV")
        evidence = self._label(prompt, r"^(E\d+): ", "Kestrel Analytics")
        reqs = re.findall(r"^(R\d+) \[", prompt, re.MULTILINE)
        body: dict[str, Any]
        if self.mode == "good":
            body = {
                "suggestions": [
                    {
                        "part": part,
                        "after": [
                            "Ran hypothesis tests on churn and cleaned six CSV sources with pandas",
                            OTHER,
                        ],
                        "reason": "Leads with the statistics this job asks for.",
                        "requirements": reqs[:1],
                        "evidence": [evidence] if evidence else [],
                    }
                ]
            }
        elif self.mode == "invent":
            body = {
                "suggestions": [
                    {
                        "part": part,
                        "after": [
                            "Built Tableau dashboards for 60 stakeholders after cleaning six CSV sources",
                            OTHER,
                        ],
                        "reason": "Matches the BI requirement.",
                        "requirements": reqs[:1],
                        "evidence": [evidence] if evidence else [],
                    }
                ]
            }
        elif self.mode == "forged":
            body = {
                "suggestions": [
                    {"part": "P99", "after": ["Invented"], "reason": "x"},
                    {
                        "part": part,
                        "after": ["Ran hypothesis tests on churn"],
                        "reason": "Shorter.",
                        "requirements": ["R99"],
                        "evidence": ["E99"],
                    },
                    {"part": part, "after": ["A second idea for the same part"], "reason": "dup"},
                ]
            }
        elif self.mode == "same":
            body = {"suggestions": [{"part": part, "after": [CLEANED, OTHER], "reason": "same"}]}
        else:
            body = {"suggestions": []}
        return GenerationResult(
            text=json.dumps(body), input_tokens=50, output_tokens=30, latency_ms=2
        )


# ------------------------------------------------------------------------------ setup


def checked_job(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str]:
    account = make_account(app)
    add_profile(account)
    job_id = read_job(engine, settings, account)
    assert start(account, job_id).status_code == 200
    run_analysis(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    return account, job_id


def resume_with_bullets(account: Account) -> dict[str, Any]:
    doc = make_doc(account, start="blank")
    content = doc["content"]
    content["header"]["name"] = "Asha Rao"
    content["sections"] = [
        {
            "id": "s1",
            "kind": "experience",
            "title": "Experience",
            "blocks": [
                {
                    "id": "b1",
                    "heading": "Data Intern",
                    "subheading": "Kestrel Analytics",
                    "dates": "2025",
                    "location": "",
                    "body": {
                        "type": "doc",
                        "content": [
                            {
                                "type": "bulletList",
                                "content": [
                                    {
                                        "type": "listItem",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": line}],
                                            }
                                        ],
                                    }
                                    for line in (CLEANED, OTHER)
                                ],
                            }
                        ],
                    },
                }
            ],
        }
    ]
    saved = save(account, doc, content)
    assert saved.status_code == 200, saved.text
    doc["revision"] = saved.json()["revision"]
    return doc


def ctx(
    engine: Engine, settings: Settings, account: Account, tailoring_id: str, *, attempt: int = 1,
    max_attempts: int = 4, seq: int | None = None, owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        row = db.execute(
            text("SELECT seq, run_id FROM resume_tailorings WHERE id = :i"), {"i": tailoring_id}
        ).one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="tailor_resume",
        args={"tailoring_id": tailoring_id, "seq": seq or row.seq}, secret={},
        attempt=attempt, max_attempts=max_attempts,
        owner_user_id=uuid.UUID(owner or account.user_id), run_id=row.run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def begin(account: Account, doc: dict[str, Any], job_id: str) -> Any:
    return account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/tailoring", json={"job_id": job_id}, headers=account.csrf
    )


def work(
    engine: Engine, settings: Settings, account: Account, started: Any, stub: Any, **kw: Any
) -> None:
    tid = started.json()["id"]
    run_tailor(ctx(engine, settings, account, tid, **kw), provider_factory=lambda: stub)


def shown(account: Account, doc: dict[str, Any], job_id: str) -> dict[str, Any]:
    response = account.client.get(
        f"{STUDIO}/resumes/{doc['id']}/tailoring", params={"job_id": job_id}
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def decide(
    account: Account, doc: dict[str, Any], body: dict[str, Any], sid: str, verb: str, **json_: Any
) -> Any:
    return account.client.post(
        f"{STUDIO}/resumes/{doc['id']}/tailoring/{body['id']}/suggestions/{sid}/{verb}",
        json=json_ or None,
        headers=account.csrf,
    )


def bullets(account: Account, doc: dict[str, Any]) -> list[str]:
    content = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    items = content["sections"][0]["blocks"][0]["body"]["content"][0]["content"]
    return [i["content"][0]["content"][0]["text"] for i in items]


@pytest.fixture
def ready(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str, dict[str, Any]]:
    account, job_id = checked_job(app, make_account, engine, settings)
    return account, job_id, resume_with_bullets(account)


# ------------------------------------------------------------------------------ starting


def test_tailoring_needs_the_job_to_be_checked_first(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    add_profile(account)
    job_id = read_job(engine, settings, account)
    doc = resume_with_bullets(account)
    response = begin(account, doc, job_id)
    assert response.status_code == 409 and response.json()["code"] == "ANALYSIS_NEEDED"
    assert account.client.get(f"{STUDIO}/tailoring/jobs").json() == []


def test_only_checked_jobs_can_be_picked(ready: tuple[Account, str, dict[str, Any]]) -> None:
    account, job_id, _ = ready
    jobs = account.client.get(f"{STUDIO}/tailoring/jobs").json()
    assert [j["job_id"] for j in jobs] == [job_id]


def test_nothing_is_shown_before_it_is_started(ready: tuple[Account, str, dict[str, Any]]) -> None:
    account, job_id, doc = ready
    response = account.client.get(
        f"{STUDIO}/resumes/{doc['id']}/tailoring", params={"job_id": job_id}
    )
    assert response.status_code == 200 and response.json() is None


# ------------------------------------------------------------------------------ the run


def test_a_good_suggestion_is_shown_with_its_reason_evidence_and_checked_claims(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    started = begin(account, doc, job_id)
    assert started.status_code == 202 and started.json()["ui_state"] == "working"
    assert started.json()["suggestions"] == []
    stub = TailorStub("good")
    work(engine, settings, account, started, stub)
    body = shown(account, doc, job_id)
    assert body["ui_state"] == "ready" and len(body["suggestions"]) == 1
    s = body["suggestions"][0]
    assert s["blocked"] is False and s["status"] == "pending" and s["edited"] is False
    assert s["before_lines"] == [CLEANED, OTHER] and s["label"] == "Data Intern, Kestrel Analytics"
    assert s["after_lines"][0].startswith("Ran hypothesis tests on churn")
    assert s["reason"] and s["requirements"] and s["citations"]
    assert all(c["supported"] for c in s["claims"])
    assert {u["text"] for u in body["unclaimed"]} >= {
        "Build dashboards in a BI tool",
        "Experience with Tableau",
    }
    prompt = stub.prompts[0]
    assert "do_not_claim" in prompt and "Experience with Tableau" in prompt


def test_an_invented_fact_is_blocked_and_the_unsupported_claims_are_named(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    work(engine, settings, account, begin(account, doc, job_id), TailorStub("invent"))
    s = shown(account, doc, job_id)["suggestions"][0]
    assert s["blocked"] is True
    unsupported = {c["text"] for c in s["claims"] if not c["supported"]}
    assert {"tableau", "60"} <= unsupported


def test_labels_the_model_made_up_and_repeats_are_dropped(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    work(engine, settings, account, begin(account, doc, job_id), TailorStub("forged"))
    body = shown(account, doc, job_id)
    assert len(body["suggestions"]) == 1
    only = body["suggestions"][0]
    assert only["after_lines"] == ["Ran hypothesis tests on churn"]
    assert only["requirements"] == [] and only["citations"] == []


def test_a_suggestion_that_changes_nothing_is_not_shown(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    work(engine, settings, account, begin(account, doc, job_id), TailorStub("same"))
    body = shown(account, doc, job_id)
    assert body["ui_state"] == "ready" and body["suggestions"] == []


def test_starting_again_replaces_the_suggestions_and_cannot_overlap(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    first = begin(account, doc, job_id)
    assert begin(account, doc, job_id).json()["code"] == "TAILORING_IN_PROGRESS"
    work(engine, settings, account, first, TailorStub("good"))
    assert len(shown(account, doc, job_id)["suggestions"]) == 1
    again = begin(account, doc, job_id)
    assert again.status_code == 202 and again.json()["suggestions"] == []
    work(engine, settings, account, again, TailorStub("invent"))
    assert shown(account, doc, job_id)["suggestions"][0]["blocked"] is True


def test_a_task_for_an_older_start_does_nothing(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    started = begin(account, doc, job_id)
    stub = TailorStub("good")
    work(engine, settings, account, started, stub, seq=99)
    assert stub.prompts == [] and shown(account, doc, job_id)["ui_state"] == "working"


# ------------------------------------------------------------------------------ failures


def test_a_missing_key_is_a_visible_failure_and_the_resume_is_untouched(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    started = begin(account, doc, job_id)

    def no_key() -> Any:
        raise LLMError("The AI provider is not configured.", retryable=False)

    run_tailor(ctx(engine, settings, account, started.json()["id"]), provider_factory=no_key)
    body = shown(account, doc, job_id)
    assert body["ui_state"] == "failed" and "not set up" in body["error_message"]
    assert bullets(account, doc) == [CLEANED, OTHER]


def test_provider_trouble_retries_then_fails_on_the_last_attempt(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, job_id, doc = ready
    started = begin(account, doc, job_id)
    with pytest.raises(TaskFailure) as raised:
        work(engine, settings, account, started, TailorStub("fail"), attempt=1)
    assert raised.value.retryable
    work(engine, settings, account, started, TailorStub("fail"), attempt=4)
    body = shown(account, doc, job_id)
    assert body["ui_state"] == "failed" and "did not answer" in body["error_message"]


# ------------------------------------------------------------------------------ deciding


def ready_suggestion(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings, mode: str
) -> tuple[Account, dict[str, Any], dict[str, Any], dict[str, Any]]:
    account, job_id, doc = ready
    work(engine, settings, account, begin(account, doc, job_id), TailorStub(mode))
    body = shown(account, doc, job_id)
    return account, doc, body, body["suggestions"][0]


def test_accepting_rewrites_that_part_keeps_a_restore_point_and_cannot_be_repeated(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    done = decide(account, doc, body, s["id"], "accept", revision=doc["revision"])
    assert done.status_code == 200, done.text
    assert done.json()["suggestion"]["status"] == "accepted"
    assert done.json()["document"]["revision"] == doc["revision"] + 1
    assert bullets(account, doc) == s["after_lines"]
    content = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    assert content["sections"][0]["blocks"][0]["heading"] == "Data Intern"
    versions = account.client.get(f"{STUDIO}/resumes/{doc['id']}/versions").json()
    assert versions and versions[0]["revision"] == doc["revision"]
    again = decide(account, doc, body, s["id"], "accept", revision=doc["revision"] + 1)
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_DECIDED"


def test_a_blocked_suggestion_can_never_be_accepted(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "invent")
    refused = decide(account, doc, body, s["id"], "accept", revision=doc["revision"])
    assert refused.status_code == 409 and refused.json()["code"] == "UNSUPPORTED_CLAIMS"
    assert bullets(account, doc) == [CLEANED, OTHER]


def test_the_stored_result_is_not_trusted_at_the_moment_of_accepting(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(
            text(
                "UPDATE tailoring_suggestions SET after_lines = CAST(:a AS jsonb), blocked = false WHERE id = :i"
            ),
            {"a": json.dumps(["Led 500 engineers at Google"]), "i": s["id"]},
        )
    refused = decide(account, doc, body, s["id"], "accept", revision=doc["revision"])
    assert refused.status_code == 409 and refused.json()["code"] == "UNSUPPORTED_CLAIMS"
    assert bullets(account, doc) == [CLEANED, OTHER]


def test_editing_a_blocked_suggestion_down_to_what_is_supported_makes_it_acceptable(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "invent")
    url = f"{STUDIO}/resumes/{doc['id']}/tailoring/{body['id']}/suggestions/{s['id']}"
    edited = account.client.put(
        url,
        json={"after_lines": ["Cleaned six CSV sources before building reports", OTHER]},
        headers=account.csrf,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["blocked"] is False and edited.json()["edited"] is True
    done = decide(account, doc, body, s["id"], "accept", revision=doc["revision"])
    assert done.status_code == 200
    assert bullets(account, doc) == ["Cleaned six CSV sources before building reports", OTHER]


def test_editing_cannot_add_a_fact_either(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    url = f"{STUDIO}/resumes/{doc['id']}/tailoring/{body['id']}/suggestions/{s['id']}"
    edited = account.client.put(
        url,
        json={"after_lines": ["Ran hypothesis tests for 900 clients at Acme"]},
        headers=account.csrf,
    )
    assert edited.json()["blocked"] is True
    assert {c["text"] for c in edited.json()["claims"] if not c["supported"]} == {"900", "acme"}
    bad = account.client.put(url, json={"after_lines": []}, headers=account.csrf)
    assert bad.status_code == 422 and "after_lines" in bad.json()["fields"]


def test_rejecting_changes_nothing_in_the_resume(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    done = decide(account, doc, body, s["id"], "reject")
    assert done.status_code == 200 and done.json()["status"] == "rejected"
    assert bullets(account, doc) == [CLEANED, OTHER]
    assert decide(account, doc, body, s["id"], "reject").json()["code"] == "ALREADY_DECIDED"


def test_a_part_that_changed_since_the_suggestion_is_refused(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    content = account.client.get(f"{STUDIO}/resumes/{doc['id']}").json()["content"]
    node = content["sections"][0]["blocks"][0]["body"]["content"][0]["content"][1]
    node["content"][0]["content"][0]["text"] = "Something I wrote since"
    saved = save(account, doc, content)
    doc["revision"] = saved.json()["revision"]
    refused = decide(account, doc, body, s["id"], "accept", revision=doc["revision"])
    assert refused.status_code == 409 and refused.json()["code"] == "RESUME_CHANGED"


def test_accepting_from_a_stale_tab_is_a_revision_conflict(
    ready: tuple[Account, str, dict[str, Any]], engine: Engine, settings: Settings
) -> None:
    account, doc, body, s = ready_suggestion(ready, engine, settings, "good")
    refused = decide(account, doc, body, s["id"], "accept", revision=doc["revision"] - 1)
    assert refused.status_code == 409 and refused.json()["code"] == "REVISION_CONFLICT"
    assert bullets(account, doc) == [CLEANED, OTHER]


# ------------------------------------------------------------------------------ isolation


def test_nobody_else_can_see_start_or_decide(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account, job_id = checked_job(app, make_account, engine, settings)
    doc = resume_with_bullets(account)
    work(engine, settings, account, begin(account, doc, job_id), TailorStub("good"))
    body = shown(account, doc, job_id)
    sid = body["suggestions"][0]["id"]
    stranger = make_account(app)
    assert stranger.client.get(f"{STUDIO}/tailoring/jobs").json() == []
    assert begin(stranger, doc, job_id).status_code == 404
    got = stranger.client.get(f"{STUDIO}/resumes/{doc['id']}/tailoring", params={"job_id": job_id})
    assert got.status_code == 404
    assert decide(stranger, doc, body, sid, "accept", revision=1).status_code == 404
    assert decide(stranger, doc, body, sid, "reject").status_code == 404
    other_doc = resume_with_bullets(stranger)
    assert begin(stranger, other_doc, job_id).status_code == 404  # the job is not theirs


def test_the_prompt_holds_only_the_owners_evidence(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    other = make_account(app)
    other.client.post(
        "/api/v1/profile/entries",
        json={"entry_type": "skill", "data": {"name": "Zebra husbandry"}},
        headers=other.csrf,
    )
    account, job_id = checked_job(app, make_account, engine, settings)
    doc = resume_with_bullets(account)
    stub = TailorStub("good")
    work(engine, settings, account, begin(account, doc, job_id), stub)
    assert "Zebra" not in stub.prompts[0]
