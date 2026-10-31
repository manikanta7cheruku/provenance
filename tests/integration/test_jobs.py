"""Checkpoint 1.8: pasting a job, reading it in the worker, the grounded result and eligibility."""

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account, new_client
from job_fixtures import BY_KEY, JobFixture
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_llm import GenerationResult, LLMError
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.extract_job import run_extract

JOBS = "/api/v1/jobs"
PREFS = "/api/v1/profile/preferences"
ENTRIES = "/api/v1/profile/entries"
MakeAccount = Callable[..., Account]


class Scripted:
    name = "stub"

    def __init__(self, *answers: str | Exception) -> None:
        self._answers = list(answers)
        self.calls = 0

    def list_models(self) -> list[Any]:
        return []

    def generate(self, **_: Any) -> GenerationResult:
        self.calls += 1
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return GenerationResult(text=answer, input_tokens=300, output_tokens=120, latency_ms=9)

    def embed(self, **_: Any) -> Any:
        raise NotImplementedError


def answer(fixture: JobFixture) -> str:
    return json.dumps(fixture.answer)


def paste(account: Account, fixture: JobFixture, source: str = "Wellfound", **extra: Any) -> Any:
    return account.client.post(
        JOBS, json={"source_name": source, "text": fixture.text, **extra}, headers=account.csrf
    )


def context(
    engine: Engine, settings: Settings, account: Account, job_id: str, *, attempt: int = 1,
    generation: int = 1, owner: str | None = None,
) -> TaskContext:  # fmt: skip
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        run_id = db.execute(
            text("SELECT run_id FROM job_postings WHERE id = :i"), {"i": job_id}
        ).scalar_one()
    return TaskContext(
        task_id=uuid.uuid4(), task_type="extract_job",
        args={"posting_id": job_id, "generation": generation}, secret={}, attempt=attempt,
        max_attempts=3, owner_user_id=uuid.UUID(owner or account.user_id), run_id=run_id,
        settings=settings.model_copy(update={"llm_model": "stub-model"}), engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )  # fmt: skip


def read(ctx: TaskContext, provider: Scripted | Exception) -> None:
    def factory() -> Scripted:
        if isinstance(provider, Exception):
            raise provider
        return provider

    run_extract(ctx, provider_factory=factory)  # type: ignore[arg-type]


def pasted_and_read(
    app: FastAPI, engine: Engine, settings: Settings, account: Account, key: str, **extra: Any
) -> str:
    fixture = BY_KEY[key]
    job_id = str(paste(account, fixture, **extra).json()["job"]["id"])
    read(context(engine, settings, account, job_id), Scripted(answer(fixture)))
    return job_id


def detail(account: Account, job_id: str) -> Any:
    response = account.client.get(f"{JOBS}/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------- schema and isolation


def test_the_tables_have_forced_security_a_unique_posting_and_sane_checks(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    paste(account, BY_KEY["india_fresher_data_analyst"])
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db:
        flags = {
            r.relname: (r.relrowsecurity, r.relforcerowsecurity)
            for r in db.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname IN ('job_postings', 'job_requirements')"
                )
            )
        }
        unique = db.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'job_postings_owner_hash_uniq'")
        ).scalar_one()
    assert flags == {"job_postings": (True, True), "job_requirements": (True, True)}
    assert "UNIQUE" in unique

    bad = {
        "a source link that is not http": "UPDATE job_postings SET source_url = 'javascript:alert(1)'",
        "text that is too short": "UPDATE job_postings SET raw_text = 'short'",
        "an unknown parse state": "UPDATE job_postings SET parse_status = 'done'",
        "a public posting": "UPDATE job_postings SET visibility = 'public'",
        "another way of acquiring": "UPDATE job_postings SET acquisition_method = 'scraped'",
    }
    for name, sql in bad.items():
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(sql))
        assert name


def test_row_level_security_hides_postings_and_requirements_from_other_tenants(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    owner, other = make_account(app), make_account(app)
    pasted_and_read(app, engine, settings, owner, "india_fresher_data_analyst")

    def visible(user_id: str | None, table: str) -> int:
        with engine.connect() as conn, conn.begin():
            if user_id is not None:
                conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": user_id})
            return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608

    for table in ("job_postings", "job_requirements"):
        assert visible(owner.user_id, table) >= 1
        assert visible(other.user_id, table) == 0
        assert visible(None, table) == 0
    with pytest.raises(DBAPIError), tenant_session(engine, uuid.UUID(other.user_id)) as db:
        db.execute(
            text(
                "INSERT INTO job_postings (owner_user_id, source_name, raw_text, content_hash) "
                "VALUES (:o, 'x', :t, :h)"
            ),
            {"o": owner.user_id, "t": "x" * 200, "h": "0" * 64},
        )


def test_another_person_gets_the_same_not_found_for_a_real_and_an_unknown_posting(
    app: FastAPI, make_account: MakeAccount
) -> None:
    owner, intruder = make_account(app), make_account(app)
    job_id = str(paste(owner, BY_KEY["india_fresher_data_analyst"]).json()["job"]["id"])
    for method, path in (
        ("get", f"{JOBS}/{job_id}"),
        ("delete", f"{JOBS}/{job_id}"),
        ("post", f"{JOBS}/{job_id}/reanalyze"),
    ):
        real = getattr(intruder.client, method)(path, headers=intruder.csrf)
        unknown = getattr(intruder.client, method)(
            path.replace(job_id, str(uuid.uuid4())), headers=intruder.csrf
        )
        assert real.status_code == unknown.status_code == 404
        assert real.json()["message"] == unknown.json()["message"]
    assert intruder.client.get(JOBS).json() == []
    assert len(owner.client.get(JOBS).json()) == 1


# --------------------------------------------------------------------- pasting


def test_pasting_stores_the_text_honest_source_labels_a_run_and_one_queued_task(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    response = paste(
        account, fixture, source="Wellfound", source_url="https://wellfound.com/jobs/123"
    )
    assert response.status_code == 201, response.text
    body = response.json()
    job = body["job"]
    assert body["duplicate"] is False
    assert (job["source_name"], job["acquisition_method"], job["visibility"]) == (
        "Wellfound",
        "user_paste",
        "private",
    )
    assert job["ui_state"] == "reading" and job["eligibility"] is None and job["requirements"] == []
    assert job["source_url"] == "https://wellfound.com/jobs/123"
    assert job["text"].startswith("Data Analyst, Early Careers")
    with Session(engine) as db:
        task = db.execute(
            text(
                "SELECT state, payload, run_id FROM tasks WHERE task_type = 'extract_job' AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).one()
    assert task.state == "queued" and task.payload["args"]["posting_id"] == job["id"]
    assert "secret" not in task.payload and fixture.text[:40] not in json.dumps(task.payload)
    labels = [r["workflow_label"] for r in account.client.get("/api/v1/runs").json()["items"]]
    assert labels == ["Reading a job posting"]


def test_pasting_the_same_posting_again_finds_the_first_and_reads_nothing_twice(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    first = paste(account, fixture)
    again = account.client.post(
        JOBS,
        json={
            "source_name": "LinkedIn",
            "text": "  " + fixture.text.upper().replace("\n", "\n\n") + "  ",
        },
        headers=account.csrf,
    )
    assert again.status_code == 200
    assert (
        again.json()["duplicate"] is True and again.json()["job"]["id"] == first.json()["job"]["id"]
    )
    assert again.json()["job"]["source_name"] == "Wellfound"  # the first label stays
    with Session(engine) as db:
        tasks = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'extract_job' AND owner_user_id = :u"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert tasks == 1


def test_two_people_pasting_the_same_text_each_get_their_own_private_copy(
    app: FastAPI, make_account: MakeAccount
) -> None:
    a, b = make_account(app), make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    id_a, id_b = paste(a, fixture).json()["job"]["id"], paste(b, fixture).json()["job"]["id"]
    assert id_a != id_b


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"source_name": "X", "text": "too short"}, "text"),
        ({"source_name": "X", "text": "word " * 5000}, "text"),
        ({"source_name": "   ", "text": "word " * 40}, "source_name"),
        (
            {"source_name": "X", "text": "word " * 40, "source_url": "javascript:alert(1)"},
            "source_url",
        ),
        ({"source_name": "X", "text": "word " * 40, "source_url": "https://a b"}, "source_url"),
        ({"text": "word " * 40}, "source_name"),
    ],
)
def test_bad_pastes_are_refused_with_a_message_on_the_right_field(
    app: FastAPI, make_account: MakeAccount, payload: dict[str, Any], field: str
) -> None:
    account = make_account(app)
    response = account.client.post(JOBS, json=payload, headers=account.csrf)
    assert response.status_code == 422
    assert field in response.json()["fields"]
    assert account.client.get(JOBS).json() == []


def test_pasting_needs_a_session_and_the_csrf_token(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    payload = {"source_name": "X", "text": BY_KEY["india_fresher_data_analyst"].text}
    assert account.client.post(JOBS, json=payload).status_code == 403
    assert new_client(app).post(JOBS, json=payload).status_code in (401, 403)
    assert new_client(app).get(JOBS).status_code == 401


def test_pasting_is_audited_without_the_text(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    paste(account, BY_KEY["india_fresher_data_analyst"], source="Wellfound")
    with Session(engine) as db:
        row = db.execute(
            text(
                "SELECT metadata::text AS m FROM audit_events WHERE actor_user_id = :u AND action = 'job.pasted'"
            ),
            {"u": account.user_id},
        ).one()
    assert "Fernlight" not in row.m and "Wellfound" in row.m


# --------------------------------------------------------------------- the worker step


def test_reading_stores_grounded_facts_and_requirements_and_records_everything(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    job_id = pasted_and_read(app, engine, settings, account, fixture.key)
    job = detail(account, job_id)
    assert job["ui_state"] == "ready" and job["title"] == "Data Analyst, Early Careers"
    assert job["company"] == "Fernlight Systems" and job["requirement_count"] == 6
    assert job["work_mode"] == "hybrid" and job["location"] == "Bengaluru, India"
    assert job["facts_dropped"] == 0 and job["requirements_dropped"] == 0
    assert job["prompt_version"] == "job-extract-1"
    kinds = {r["text"]: r["kind"] for r in job["requirements"]}
    assert (
        kinds["Experience with Tableau"] == "preferred"
        and kinds["Strong SQL and Python (pandas)"] == "required"
    )
    for r in job["requirements"]:
        assert job["text"][r["quote_start"] : r["quote_end"]] == r["quote"]
    assert job["facts"]["work_mode"]["quote"] == "Bengaluru, India (Hybrid)"

    run = account.client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert run["run"]["ui_state"] == "completed"
    assert [s["step_name"] for s in run["steps"]] == [
        "read_posting",
        "extract_requirements",
        "check_quotes",
        "save_analysis",
    ]
    assert [c["purpose"] for c in run["llm_calls"]] == ["job_extraction"]
    assert "Fernlight" not in json.dumps(run)


def test_reading_twice_leaves_one_result_and_a_stale_or_foreign_task_does_nothing(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account, other = make_account(app), make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    job_id = str(paste(account, fixture).json()["job"]["id"])
    ctx = context(engine, settings, account, job_id)
    read(ctx, Scripted(answer(fixture)))
    read(ctx, Scripted(answer(fixture)))
    assert detail(account, job_id)["requirement_count"] == 6

    stale = Scripted(answer(fixture))
    read(context(engine, settings, account, job_id, generation=9), stale)
    foreign = context(engine, settings, account, job_id, owner=other.user_id)
    read(foreign, stale)
    assert stale.calls == 0

    account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf)
    read(ctx, stale)
    assert stale.calls == 0


def test_changing_an_answer_changes_the_eligibility_without_reading_the_posting_again(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = pasted_and_read(app, engine, settings, account, "us_only_senior_no_sponsorship")

    def gates() -> dict[str, str]:
        return {
            g["gate"]: g["state"] for g in detail(account, job_id)["eligibility_detail"]["gates"]
        }

    before = gates()
    assert (
        before["authorization"] == "requires_user_input"
    )  # says no sponsorship, asks whether you need it
    account.client.put(
        PREFS,
        json={"needs_sponsorship": True, "authorized_countries": ["India"]},
        headers=account.csrf,
    )
    after = detail(account, job_id)
    assert {g["gate"]: g["state"] for g in after["eligibility_detail"]["gates"]}[
        "authorization"
    ] == "not_eligible"
    assert after["eligibility"] == "not_eligible"
    first = after["eligibility_detail"]["gates"][0]
    assert first["state"] == "not_eligible"  # a blocker is listed first, never buried
    assert first["posting_quote"] and first["posting_quote"] in after["text"]
    account.client.put(
        PREFS,
        json={"needs_sponsorship": False, "authorized_countries": ["United States"]},
        headers=account.csrf,
    )
    assert gates()["authorization"] == "eligible"


def test_experience_years_come_from_the_dates_on_the_profile(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = pasted_and_read(app, engine, settings, account, "lead_with_a_hard_years_requirement")

    def seniority() -> dict[str, Any]:
        return next(
            g
            for g in detail(account, job_id)["eligibility_detail"]["gates"]
            if g["gate"] == "seniority"
        )

    assert (
        seniority()["state"] == "requires_user_input"
    )  # no dated experience, and 8 years is asked
    account.client.post(ENTRIES, json={"entry_type": "internship", "data": {
        "company": "Kestrel", "title": "Intern", "start_date": "2025-06", "end_date": "2025-08"}}, headers=account.csrf)  # fmt: skip
    gate = seniority()
    assert gate["state"] == "not_eligible" and "about 0.2" in gate["reason"]


def test_a_hard_exclusion_names_where_it_was_found(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = pasted_and_read(app, engine, settings, account, "lead_with_a_hard_years_requirement")
    account.client.put(PREFS, json={"exclusions": ["system design"]}, headers=account.csrf)
    gate = next(
        g
        for g in detail(account, job_id)["eligibility_detail"]["gates"]
        if g["gate"] == "exclusions"
    )
    assert gate["state"] == "not_eligible" and "system design" in gate["posting_quote"].lower()


def test_the_list_shows_state_and_eligibility_for_each_posting(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    pasted_and_read(app, engine, settings, account, "india_fresher_data_analyst")
    paste(account, BY_KEY["us_only_senior_no_sponsorship"])  # still being read
    rows = {r["company"] or "pending": r for r in account.client.get(JOBS).json()}
    assert (
        rows["Fernlight Systems"]["ui_state"] == "ready"
        and rows["Fernlight Systems"]["eligibility"] is not None
    )
    assert rows["pending"]["ui_state"] == "reading" and rows["pending"]["eligibility"] is None
    assert rows["Fernlight Systems"]["acquisition_method"] == "user_paste"


# --------------------------------------------------------------------- what the model gets wrong


def test_a_posting_that_tries_to_give_instructions_cannot_add_requirements_that_are_not_quotes(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = pasted_and_read(
        app, engine, settings, account, "prompt_injection_obeyed_by_a_bad_model"
    )
    job = detail(account, job_id)
    assert job["requirements_dropped"] == 1
    assert not any("5 crore" in r["text"] for r in job["requirements"])


def test_invented_quotes_and_values_are_dropped_and_the_screen_can_say_how_many(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job = detail(
        account, pasted_and_read(app, engine, settings, account, "fabricated_quotes_and_values")
    )
    assert (job["facts_dropped"], job["requirements_dropped"], job["requirement_count"]) == (
        3,
        2,
        2,
    )
    assert set(job["facts"]) == {"location"}


def test_garbage_from_the_model_marks_the_posting_failed_with_a_plain_message(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = str(paste(account, BY_KEY["india_fresher_data_analyst"]).json()["job"]["id"])
    read(context(engine, settings, account, job_id), Scripted("nope", "still nope"))
    job = detail(account, job_id)
    assert (
        job["ui_state"] == "failed"
        and job["can_retry"] is True
        and "Your posting is saved" in job["error_message"]
    )
    run = account.client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert run["run"]["ui_state"] == "retry_available" and len(run["llm_calls"]) == 2


def test_an_answer_with_nothing_found_in_the_posting_fails_for_the_right_reason(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    empty = json.dumps({"facts": {}, "requirements": []})
    job_id = str(paste(account, fixture).json()["job"]["id"])
    read(context(engine, settings, account, job_id), Scripted(empty))
    assert "could not find any requirements" in detail(account, job_id)["error_message"]

    made_up = json.dumps(
        {
            "facts": {},
            "requirements": [
                {
                    "text": "Rust",
                    "kind": "required",
                    "category": "skill",
                    "years_min": None,
                    "quote": "needs Rust",
                }
            ],
        }
    )
    other = BY_KEY["us_only_senior_no_sponsorship"]
    second = str(paste(account, other).json()["job"]["id"])
    read(context(engine, settings, account, second), Scripted(made_up))
    job = detail(account, second)
    assert job["ui_state"] == "failed" and "could not turn this posting" in job["error_message"]


def test_a_provider_that_is_not_set_up_is_a_visible_retryable_failure(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = str(paste(account, BY_KEY["india_fresher_data_analyst"]).json()["job"]["id"])
    read(context(engine, settings, account, job_id), LLMError("not configured", retryable=False))
    job = detail(account, job_id)
    assert "not set up" in job["error_message"] and job["can_retry"] is True


def test_a_busy_provider_is_retried_and_fails_visibly_only_on_the_last_attempt(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    job_id = str(paste(account, BY_KEY["india_fresher_data_analyst"]).json()["job"]["id"])
    busy = LLMError("busy", retryable=True)
    with pytest.raises(TaskFailure) as caught:
        read(context(engine, settings, account, job_id, attempt=1), Scripted(busy))
    assert caught.value.retryable is True
    assert detail(account, job_id)["ui_state"] == "reading"
    read(context(engine, settings, account, job_id, attempt=3), Scripted(busy))
    assert detail(account, job_id)["ui_state"] == "failed"


# --------------------------------------------------------------------- re-reading and deleting


def test_reading_again_is_only_allowed_when_idle_and_replaces_the_result(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    fixture = BY_KEY["india_fresher_data_analyst"]
    job_id = str(paste(account, fixture).json()["job"]["id"])
    early = account.client.post(f"{JOBS}/{job_id}/reanalyze", headers=account.csrf)
    assert early.status_code == 409 and early.json()["code"] == "PARSE_IN_PROGRESS"
    read(context(engine, settings, account, job_id), Scripted(answer(fixture)))
    again = account.client.post(f"{JOBS}/{job_id}/reanalyze", headers=account.csrf)
    assert again.status_code == 200 and again.json()["ui_state"] == "reading"
    smaller = json.dumps(
        {"facts": fixture.answer["facts"], "requirements": fixture.answer["requirements"][:2]}
    )
    read(context(engine, settings, account, job_id, generation=2), Scripted(smaller))
    assert detail(account, job_id)["requirement_count"] == 2


def test_deleting_removes_the_posting_and_its_requirements_and_cancels_a_waiting_read(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    read_id = pasted_and_read(app, engine, settings, account, "india_fresher_data_analyst")
    waiting_id = str(paste(account, BY_KEY["us_only_senior_no_sponsorship"]).json()["job"]["id"])
    for job_id in (read_id, waiting_id):
        assert account.client.delete(f"{JOBS}/{job_id}", headers=account.csrf).status_code == 204
        assert account.client.get(f"{JOBS}/{job_id}").status_code == 404
    assert rows_count(engine, account, "job_requirements") == 0
    with Session(engine) as db:
        state = db.execute(
            text(
                "SELECT state FROM tasks WHERE task_type = 'extract_job' AND owner_user_id = :u "
                "AND payload->'args'->>'posting_id' = :p"
            ),
            {"u": account.user_id, "p": waiting_id},
        ).scalar_one()
        audit = db.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE actor_user_id = :u AND action = 'job.deleted'"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert state == "cancelled" and audit == 2


def rows_count(engine: Engine, account: Account, table: str) -> int:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return int(db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def test_pasting_is_rate_limited(
    build_app: Callable[..., FastAPI], make_account: MakeAccount, storage: Any
) -> None:
    from helpers import generous_policies

    from pv_domain.ratelimit import RatePolicy

    policies = generous_policies()
    policies["job_paste_user"] = RatePolicy("job_paste_user", 2, 60)
    app = build_app(policies=policies, storage=storage)
    account = make_account(app)
    texts = [
        BY_KEY[k]
        for k in (
            "india_fresher_data_analyst",
            "us_only_senior_no_sponsorship",
            "canada_internship",
        )
    ]
    assert [paste(account, f).status_code for f in texts] == [201, 201, 429]
