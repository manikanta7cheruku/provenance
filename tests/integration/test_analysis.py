"""Checkpoint 1.9: the evidence check of a job, the agent in the worker, scoring, questions, feedback."""

import json
import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account
from job_fixtures import BY_KEY
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.analyze_job import run_analyze
from pv_worker.handlers.extract_job import run_extract

JOBS = "/api/v1/jobs"
ENTRIES = "/api/v1/profile/entries"
PREFS = "/api/v1/profile/preferences"
MakeAccount = Callable[..., Account]

SQL = "Strong SQL and Python (pandas)"
BI = "Build dashboards in a BI tool"
STATS = "Statistics including hypothesis testing"
QUERY = "Write SQL to answer product questions"
TABLEAU = "Experience with Tableau"
CLEANED = "Cleaned six CSV sources with pandas and ran hypothesis tests on churn"
TESTS = "ran hypothesis tests on churn"


class Reader:
    """Stands in for the model that reads the posting (checkpoint 1.8)."""

    name = "stub"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def list_models(self) -> list[Any]:
        return []

    def generate(self, **_: Any) -> GenerationResult:
        return GenerationResult(
            text=json.dumps(self._payload), input_tokens=1, output_tokens=1, latency_ms=1
        )

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError


class AgentStub:
    """Stands in for the model inside the agent. A plan maps a part of the requirement text to what
    it does: ("cite", verdict, kind, snippet of evidence, quote), ("ask", question), ("none",),
    ("fail",) for a provider outage, or ("forge", label) to cite evidence that was never shown."""

    name = "stub"

    def __init__(self, plan: dict[str, tuple[Any, ...]]) -> None:
        self.plan = plan
        self.seen: list[str] = []
        self.prompts: list[str] = []

    def list_models(self) -> list[Any]:
        return []

    def _label_for(self, prompt: str, snippet: str) -> str | None:
        for line in prompt.splitlines():
            found = re.match(r"\[(E\d+)\] .*", line)
            if found and snippet in line:
                return found.group(1)
        return None

    def generate(self, *, prompt: str, **_: Any) -> GenerationResult:
        self.prompts.append(prompt)
        head = prompt.splitlines()[0]
        key = next((k for k in self.plan if k in head), None)
        self.seen.append(key or "?")
        step = self.plan.get(key or "", ("none",))
        body: dict[str, Any]
        if step[0] == "fail":
            raise LLMError("busy", retryable=True)
        if step[0] == "ask" and "may not ask" not in prompt:
            body = {"action": "ask_user", "question": step[1]}
        elif step[0] == "cite":
            _, verdict, kind, snippet, quote = step
            label = self._label_for(prompt, snippet)
            if label is None:
                body = {"action": "verdict", "verdict": "not_verified", "reason": "nothing found"}
            else:
                body = {
                    "action": "verdict",
                    "verdict": verdict,
                    "evidence_kind": kind,
                    "citations": [{"evidence": label, "quote": quote}],
                    "reason": "The entry says so.",
                }
        elif step[0] == "forge":
            body = {
                "action": "verdict",
                "verdict": "met",
                "evidence_kind": "direct",
                "citations": [{"evidence": step[1], "quote": "anything at all"}],
                "reason": "Trust me.",
            }
        else:
            body = {"action": "verdict", "verdict": "not_verified", "reason": "nothing found"}
        return GenerationResult(
            text=json.dumps(body), input_tokens=40, output_tokens=20, latency_ms=2
        )

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError


FULL_PLAN: dict[str, tuple[Any, ...]] = {
    QUERY: ("cite", "met", "direct", "Skill: SQL", "Skill: SQL"),
    BI: ("none",),
    SQL: ("cite", "met", "direct", "Skill: Python", "Skill: Python"),
    STATS: ("cite", "partial", "direct", "hypothesis tests", TESTS),
    TABLEAU: ("none",),
}


def ctx(
    engine: Engine, settings: Settings, account: Account, job_id: str, *, attempt: int = 1,
    max_attempts: int = 4, seq: int | None = None, owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        row = db.execute(
            text("SELECT id, resume_seq, run_id FROM job_analyses WHERE posting_id = :p"),
            {"p": job_id},
        ).one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="analyze_job",
        args={"analysis_id": str(row.id), "seq": seq or row.resume_seq}, secret={},
        attempt=attempt, max_attempts=max_attempts,
        owner_user_id=uuid.UUID(owner or account.user_id), run_id=row.run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def read_job(
    engine: Engine, settings: Settings, account: Account, key: str = "india_fresher_data_analyst"
) -> str:
    fixture = BY_KEY[key]
    response = account.client.post(
        JOBS, json={"source_name": "Wellfound", "text": fixture.text}, headers=account.csrf
    )
    job_id = str(response.json()["job"]["id"])
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        run_id = db.execute(
            text("SELECT run_id FROM job_postings WHERE id = :i"), {"i": job_id}
        ).scalar_one()
    task = TaskContext(
        task_id=uuid.uuid4(), task_type="extract_job",
        args={"posting_id": job_id, "generation": 1}, secret={}, attempt=1, max_attempts=3,
        owner_user_id=uuid.UUID(account.user_id), run_id=run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip
    run_extract(task, provider_factory=lambda: Reader(fixture.answer))  # type: ignore[arg-type,return-value]
    return job_id


def add_profile(account: Account) -> None:
    for entry in (
        {"entry_type": "skill", "data": {"name": "SQL"}},
        {"entry_type": "skill", "data": {"name": "Python"}},
        {
            "entry_type": "internship",
            "data": {
                "company": "Kestrel Analytics",
                "title": "Data Intern",
                "highlights": [CLEANED],
            },
        },
    ):
        assert account.client.post(ENTRIES, json=entry, headers=account.csrf).status_code == 201


def start(account: Account, job_id: str) -> Any:
    return account.client.post(f"{JOBS}/{job_id}/analysis", headers=account.csrf)


def view(account: Account, job_id: str) -> Any:
    response = account.client.get(f"{JOBS}/{job_id}/analysis")
    assert response.status_code == 200, response.text
    return response.json()


def run(
    engine: Engine, settings: Settings, account: Account, job_id: str, agent: AgentStub, **kw: Any
) -> None:
    run_analyze(ctx(engine, settings, account, job_id, **kw), provider_factory=lambda: agent)  # type: ignore[arg-type,return-value]


def verdicts(body: Any) -> dict[str, dict[str, Any]]:
    return {v["requirement"]: v for v in body["verdicts"]}


@pytest.fixture
def ready(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> tuple[Account, str]:
    account = make_account(app)
    add_profile(account)
    return account, read_job(engine, settings, account)


# ------------------------------------------------------------------------------ starting


def test_the_check_has_not_started_and_says_what_blocks_it(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = read_job(engine, settings, account)
    body = view(account, job_id)
    assert body["ui_state"] == "not_started" and body["can_start"] is False
    assert "Add your resume or a profile entry" in body["blocker"]
    response = start(account, job_id)
    assert response.status_code == 409 and response.json()["code"] == "NO_EVIDENCE"
    assert [r["requirement"] for r in body["gate_requirements"]] == ["Authorized to work in India"]
    assert len(body["verdicts"]) == 5 and all(v["verdict"] is None for v in body["verdicts"])


def test_a_job_that_is_not_read_yet_cannot_be_checked(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    add_profile(account)
    fixture = BY_KEY["india_fresher_data_analyst"]
    job_id = account.client.post(
        JOBS, json={"source_name": "Other", "text": fixture.text}, headers=account.csrf
    ).json()["job"]["id"]
    assert start(account, job_id).json()["code"] == "JOB_NOT_READY"


def test_a_failed_hard_gate_means_no_check_and_no_score(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    add_profile(account)
    job_id = read_job(engine, settings, account, "us_only_senior_no_sponsorship")
    account.client.put(
        PREFS,
        json={"authorized_countries": ["India"], "needs_sponsorship": True},
        headers=account.csrf,
    )
    response = start(account, job_id)
    assert response.status_code == 409 and response.json()["code"] == "NOT_ELIGIBLE"


# -------------------------------------------------------------------------- the whole run


def test_a_full_run_stores_verified_verdicts_and_shows_a_band_with_reasons(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    started = start(account, job_id)
    assert started.status_code == 200 and started.json()["ui_state"] == "working"
    agent = AgentStub(FULL_PLAN)
    run(engine, settings, account, job_id, agent)

    body = view(account, job_id)
    assert body["ui_state"] == "ready" and body["checked"] == body["total"] == 5
    v = verdicts(body)
    assert v[QUERY]["verdict"] == "met" and v[QUERY]["confidence"] == "high"
    assert v[QUERY]["citations"][0]["quote"] == "Skill: SQL"
    assert (
        v[QUERY]["citations"][0]["source"] == "profile" and not v[QUERY]["citations"][0]["changed"]
    )
    assert v[STATS]["verdict"] == "partial" and v[STATS]["confidence"] == "medium"
    assert v[BI]["verdict"] == "not_verified" and v[BI]["confidence"] == "none"
    assert v[BI]["reason"] == "Nothing in your profile supports this yet."
    assert not v[BI]["citations"]
    # Required items come first, then nice-to-haves.
    assert [x["kind"] for x in body["verdicts"]] == ["required"] * 4 + ["preferred"]

    score = body["score"]
    assert score["scoring_version"] == "scoring-1" and score["required_total"] == 4
    assert (score["met"], score["partial"], score["not_verified"]) == (2, 1, 1)
    assert score["band"] == "good"  # 2.5 of 4 supported is 0.625
    assert any("3 of 4 required requirements supported" in r for r in score["reasons"])
    assert [g["requirement"] for g in body["gaps"]] == [BI, STATS]
    assert body["stale"] is False and body["prompt_version"] == "evidence-agent-1"

    # Every call is in the ledger and none of it holds text.
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        rows = db.execute(
            text(
                "SELECT count(*), bool_and(content_hash IS NOT NULL) FROM llm_calls "
                "WHERE user_id = :u AND purpose = 'evidence_agent'"
            ),
            {"u": account.user_id},
        ).one()
        assert rows[0] == len(agent.prompts) and rows[1] is True
        steps = (
            db.execute(
                text(
                    "SELECT step_name FROM workflow_steps WHERE owner_user_id = :u ORDER BY ordinal"
                ),
                {"u": account.user_id},
            )
            .scalars()
            .all()
        )
    assert "check_requirements" in steps


def test_the_band_is_computed_on_read_so_a_new_answer_changes_it_at_once(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    assert view(account, job_id)["score"]["band"] == "good"
    # The person now lists something the posting mentions among the things they want to avoid.
    account.client.put(PREFS, json={"exclusions": ["Tableau"]}, headers=account.csrf)
    gated = view(account, job_id)["score"]
    assert gated["band"] == "not_eligible"
    assert gated["reasons"][1] == "No score is shown while a hard requirement is not met."


def test_a_citation_the_agent_never_saw_is_refused_and_the_requirement_stays_unverified(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    plan = {**FULL_PLAN, QUERY: ("forge", "E42")}
    run(engine, settings, account, job_id, AgentStub(plan))
    forged = verdicts(view(account, job_id))[QUERY]
    assert forged["verdict"] == "not_verified" and forged["citations"] == []
    assert (
        forged["reason"] == "The reader named evidence that could not be confirmed in your profile."
    )
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        met_without = db.execute(
            text(
                "SELECT count(*) FROM requirement_verdicts WHERE verdict <> 'not_verified' AND citations = '[]'"
            )
        ).scalar_one()
    assert met_without == 0


def test_editing_a_cited_entry_marks_the_check_as_out_of_date(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    entries = account.client.get(ENTRIES).json()
    python = next(e for e in entries if e["data"].get("name") == "Python")
    account.client.patch(
        f"{ENTRIES}/{python['id']}", json={"data": {"name": "Python 3"}}, headers=account.csrf
    )
    body = view(account, job_id)
    assert body["stale"] is True
    assert verdicts(body)[SQL]["citations"][0]["changed"] is True
    assert verdicts(body)[QUERY]["citations"][0]["changed"] is False


def test_checking_again_after_a_completed_run_starts_over(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    again = start(account, job_id)
    assert again.status_code == 200 and again.json()["ui_state"] == "working"
    assert again.json()["checked"] == 0
    assert start(account, job_id).json()["code"] == "ANALYSIS_IN_PROGRESS"


def test_a_task_for_an_older_start_or_another_owner_does_nothing(
    ready: tuple[Account, str],
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
) -> None:
    account, job_id = ready
    start(account, job_id)
    agent = AgentStub(FULL_PLAN)
    run(engine, settings, account, job_id, agent, seq=99)
    assert agent.prompts == [] and view(account, job_id)["checked"] == 0
    other = make_account(app)
    run(engine, settings, account, job_id, agent, owner=other.user_id)
    assert agent.prompts == [] and view(account, job_id)["checked"] == 0


# ----------------------------------------------------------------- failure and resuming


def test_no_ai_key_is_a_visible_failure_with_a_plain_message(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)

    def missing() -> Any:
        raise LLMError("no key", retryable=False)

    run_analyze(ctx(engine, settings, account, job_id), provider_factory=missing)
    body = view(account, job_id)
    assert body["ui_state"] == "failed" and "not set up yet" in body["error_message"]
    assert body["can_start"] is True


def test_a_worker_that_dies_midway_resumes_without_redoing_finished_requirements(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    # The provider goes down while the SECOND requirement is being checked.
    first = AgentStub({**FULL_PLAN, BI: ("fail",)})
    with pytest.raises(TaskFailure) as raised:
        run(engine, settings, account, job_id, first, attempt=1)
    assert raised.value.retryable is True
    partial = view(account, job_id)
    assert partial["checked"] == 1 and partial["ui_state"] == "working" and partial["score"] is None
    done_before = {r for r, v in verdicts(partial).items() if v["verdict"]}

    # A new worker takes over: only what is missing is checked.
    second = AgentStub(FULL_PLAN)
    run(engine, settings, account, job_id, second, attempt=2)
    assert QUERY not in second.seen and set(second.seen) == {BI, SQL, STATS, TABLEAU}
    final = view(account, job_id)
    assert final["ui_state"] == "ready" and final["checked"] == 5
    assert done_before <= {r for r, v in verdicts(final).items() if v["verdict"]}


def test_the_last_attempt_fails_visibly_and_keeps_the_verdicts_already_earned(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub({**FULL_PLAN, BI: ("fail",)}), attempt=4)
    body = view(account, job_id)
    assert body["ui_state"] == "failed" and "continues where it stopped" in body["error_message"]
    assert body["checked"] == 1
    # Checking again continues instead of starting over.
    again = start(account, job_id).json()
    assert again["checked"] == 1 and again["ui_state"] == "working"


# ---------------------------------------------------------------- asking the person


def ask_plan() -> dict[str, tuple[Any, ...]]:
    return {**FULL_PLAN, BI: ("ask", "Have you built dashboards in a course or project?")}


def test_the_agent_can_ask_and_the_answer_becomes_evidence_that_settles_it(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(ask_plan()))
    body = view(account, job_id)
    assert body["ui_state"] == "needs_answer" and body["score"] is None
    assert body["checked"] == 4  # everything else finished
    question = body["questions"][0]
    assert question["status"] == "pending" and question["requirement"] == BI
    assert verdicts(body)[BI]["verdict"] is None
    assert start(account, job_id).json()["code"] == "NEEDS_ANSWER"

    answered = account.client.post(
        f"{JOBS}/{job_id}/analysis/questions/{question['id']}/answer",
        json={
            "answer": "I built three Power BI dashboards for my final year project on sales data."
        },
        headers=account.csrf,
    )
    assert answered.status_code == 200 and answered.json()["ui_state"] == "working"
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        chunk = db.execute(
            text(
                "SELECT text, source_type FROM evidence_chunks WHERE source_type = 'user_answer' AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).one()
    assert chunk.text.startswith("In my own words: I built three Power BI dashboards")

    # The new task finds the answer by search and cites it. It cannot ask a second time.
    plan = {
        **FULL_PLAN,
        BI: ("cite", "met", "direct", "Power BI dashboards", "built three Power BI dashboards"),
    }
    resumed = AgentStub(plan)
    run(engine, settings, account, job_id, resumed)
    assert resumed.seen == [BI]
    final = view(account, job_id)
    assert final["ui_state"] == "ready"
    cited = verdicts(final)[BI]["citations"][0]
    assert cited["source"] == "answer" and verdicts(final)[BI]["verdict"] == "met"
    assert final["questions"][0]["status"] == "answered"
    assert final["score"]["met"] == 3


def test_skipping_a_question_leaves_the_requirement_unverified_and_finishes_the_check(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(ask_plan()))
    question = view(account, job_id)["questions"][0]
    skipped = account.client.post(
        f"{JOBS}/{job_id}/analysis/questions/{question['id']}/skip", headers=account.csrf
    )
    body = skipped.json()
    assert skipped.status_code == 200 and body["ui_state"] == "ready"
    assert verdicts(body)[BI]["verdict"] == "not_verified"
    assert verdicts(body)[BI]["reason"] == "You chose not to answer, so this stays unverified."
    again = account.client.post(
        f"{JOBS}/{job_id}/analysis/questions/{question['id']}/skip", headers=account.csrf
    )
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_ANSWERED"


def test_an_answer_must_be_text_and_the_question_must_be_yours(
    ready: tuple[Account, str],
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(ask_plan()))
    question = view(account, job_id)["questions"][0]
    url = f"{JOBS}/{job_id}/analysis/questions/{question['id']}/answer"
    too_long = account.client.post(url, json={"answer": "x" * 1500}, headers=account.csrf)
    assert too_long.status_code == 422 and "answer" in too_long.json()["fields"]
    blank = account.client.post(url, json={"answer": "   "}, headers=account.csrf)
    assert blank.status_code == 422
    stranger = make_account(app)
    assert (
        stranger.client.post(url, json={"answer": "hi"}, headers=stranger.csrf).status_code == 404
    )


# --------------------------------------------------------------------------- feedback


def test_feedback_is_kept_with_the_versions_and_answering_again_replaces_it(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    body = view(account, job_id)
    req_id = verdicts(body)[QUERY]["requirement_id"]
    url = f"{JOBS}/{job_id}/analysis/feedback"
    first = account.client.post(
        url,
        json={"requirement_id": req_id, "answer": "wrong", "note": "  not  quite "},
        headers=account.csrf,
    )
    assert first.status_code == 200 and verdicts(first.json())[QUERY]["feedback"] == "wrong"
    second = account.client.post(
        url, json={"requirement_id": req_id, "answer": "right"}, headers=account.csrf
    )
    assert verdicts(second.json())[QUERY]["feedback"] == "right"
    whole = account.client.post(url, json={"answer": "right"}, headers=account.csrf)
    assert whole.json()["recommendation_feedback"] == "right"
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        rows = db.execute(
            text(
                "SELECT subject, shown, answer, note, scoring_version, prompt_version FROM verdict_feedback ORDER BY subject"
            )
        ).all()
    assert [(r.subject, r.shown, r.answer) for r in rows] == [
        ("recommendation", "good", "right"),
        ("verdict", "met", "right"),
    ]
    assert all(
        r.scoring_version == "scoring-1" and r.prompt_version == "evidence-agent-1" for r in rows
    )


def test_feedback_needs_something_to_rate(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    url = f"{JOBS}/{job_id}/analysis/feedback"
    assert (
        account.client.post(url, json={"answer": "right"}, headers=account.csrf).status_code == 409
    )
    unknown = account.client.post(
        url, json={"requirement_id": str(uuid.uuid4()), "answer": "right"}, headers=account.csrf
    )
    assert unknown.status_code == 404


# --------------------------------------------------------------- isolation and cleanup


def test_tables_are_protected_by_row_level_security_for_other_tenants_and_forged_rows(
    ready: tuple[Account, str],
    app: FastAPI,
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    other = make_account(app)
    tables = ("job_analyses", "requirement_verdicts", "agent_questions", "verdict_feedback")
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
    for table in tables:
        with tenant_session(engine, uuid.UUID(other.user_id)) as db:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608
    with pytest.raises(DBAPIError), tenant_session(engine, uuid.UUID(other.user_id)) as db:
        db.execute(
            text("INSERT INTO job_analyses (owner_user_id, posting_id) VALUES (:o, :p)"),
            {"o": account.user_id, "p": job_id},
        )


def test_another_person_gets_not_found_for_every_analysis_route(
    ready: tuple[Account, str], app: FastAPI, make_account: MakeAccount
) -> None:
    _, job_id = ready
    stranger = make_account(app)
    url = f"{JOBS}/{job_id}/analysis"
    assert stranger.client.get(url).status_code == 404
    assert stranger.client.post(url, headers=stranger.csrf).status_code == 404
    assert (
        stranger.client.post(
            f"{url}/feedback", json={"answer": "right"}, headers=stranger.csrf
        ).status_code
        == 404
    )


def test_the_routes_need_a_session_and_the_csrf_token(
    ready: tuple[Account, str], app: FastAPI
) -> None:
    from fastapi.testclient import TestClient

    account, job_id = ready
    assert TestClient(app).get(f"{JOBS}/{job_id}/analysis").status_code == 401
    assert account.client.post(f"{JOBS}/{job_id}/analysis").status_code in (401, 403)


def test_deleting_the_job_deletes_the_answers_given_for_it(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(ask_plan()))
    question = view(account, job_id)["questions"][0]
    account.client.post(
        f"{JOBS}/{job_id}/analysis/questions/{question['id']}/answer",
        json={"answer": "I built dashboards."},
        headers=account.csrf,
    )
    assert account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf).status_code == 204
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        left = db.execute(
            text(
                "SELECT count(*) FROM evidence_chunks WHERE owner_user_id = :u AND source_type = 'user_answer'"
            ),
            {"u": account.user_id},
        ).scalar_one()
        queued = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'analyze_job' AND state = 'queued' AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert left == 0 and queued == 0


def test_reading_the_posting_again_drops_the_old_check_because_its_requirements_are_gone(
    ready: tuple[Account, str], engine: Engine, settings: Settings
) -> None:
    account, job_id = ready
    start(account, job_id)
    run(engine, settings, account, job_id, AgentStub(FULL_PLAN))
    assert view(account, job_id)["ui_state"] == "ready"
    assert (
        account.client.post(f"{JOBS}/{job_id}/reanalyze", headers=account.csrf).status_code == 200
    )
    fixture = BY_KEY["india_fresher_data_analyst"]
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        run_id = db.execute(
            text("SELECT run_id FROM job_postings WHERE id = :i"), {"i": job_id}
        ).scalar_one()
    task = TaskContext(
        task_id=uuid.uuid4(), task_type="extract_job", args={"posting_id": job_id, "generation": 2},
        secret={}, attempt=1, max_attempts=3, owner_user_id=uuid.UUID(account.user_id), run_id=run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip
    run_extract(task, provider_factory=lambda: Reader(fixture.answer))  # type: ignore[arg-type,return-value]
    assert view(account, job_id)["ui_state"] == "not_started"


def test_starting_answering_and_feedback_have_rate_limits() -> None:
    from pv_domain.ratelimit import DEFAULT_POLICIES

    assert DEFAULT_POLICIES["analysis_start_user"].limit == 20
    assert DEFAULT_POLICIES["analysis_answer_user"].limit == 60
    assert DEFAULT_POLICIES["analysis_feedback_user"].limit == 120
