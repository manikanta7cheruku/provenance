"""Checkpoint 1.7: evidence chunks, embeddings and hybrid retrieval, against real PostgreSQL.

The embedding model is replaced by a deterministic bag-of-words stand-in, so vector search is
real (pgvector, cosine, HNSW) while the tests stay free and repeatable.
"""

import hashlib
import math
import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from helpers import Account, generous_policies, new_client
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pv_config import Settings
from pv_domain.ratelimit import RatePolicy
from pv_llm import EmbeddingResult, LLMError, hybrid_search
from pv_persistence.evidence import (
    evidence_status,
    pending_embeddings,
    reconcile_profile_chunks,
    store_embedding,
    sync_evidence,
)
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import TaskContext, TaskFailure
from pv_worker.handlers.embed_evidence import run_embed

ENTRIES = "/api/v1/profile/entries"
MakeAccount = Callable[..., Account]
MODEL = "embed-stub"

_STOP = {"the", "and", "for", "with", "that", "this", "from", "was", "are", "you", "your"}


class BagOfWords:
    """A tiny deterministic embedder: words that overlap give vectors that point the same way."""

    name = "stub"

    def __init__(
        self, *, fail: Exception | None = None, size: int = 768, fail_after: int | None = None
    ) -> None:
        self.calls: list[str] = []
        self._fail = fail
        self._size = size
        self._fail_after = fail_after

    def embed(self, *, model: str, text: str, dimensions: int | None = None) -> EmbeddingResult:
        if self._fail is not None and (
            self._fail_after is None or len(self.calls) >= self._fail_after
        ):
            raise self._fail
        self.calls.append(text)
        vector = [0.0] * self._size
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            if len(word) > 2 and word not in _STOP:
                vector[
                    int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
                    % self._size
                ] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return EmbeddingResult(
            values=[v / norm for v in vector], input_tokens=len(text.split()), latency_ms=1
        )

    def generate(self, **_: Any) -> Any:
        raise NotImplementedError

    def list_models(self) -> list[Any]:
        return []


def configured(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"gemini_api_key": SecretStr("test-key"), "llm_embedding_model": MODEL}
    )


def add(account: Account, entry_type: str, data: dict[str, Any]) -> str:
    response = account.client.post(
        ENTRIES, json={"entry_type": entry_type, "data": data}, headers=account.csrf
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def rows(engine: Engine, account: Account, sql: str, **params: Any) -> list[Any]:
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        return list(db.execute(text(sql), params).all())


def chunk_texts(engine: Engine, account: Account) -> list[str]:
    return [r.text for r in rows(engine, account, "SELECT text FROM evidence_chunks ORDER BY text")]


def embed_ctx(engine: Engine, settings: Settings, account: Account) -> TaskContext:
    return TaskContext(
        task_id=uuid.uuid4(),
        task_type="embed_evidence",
        args={},
        secret={},
        attempt=1,
        max_attempts=5,
        owner_user_id=uuid.UUID(account.user_id),
        run_id=None,
        settings=settings,
        engine=engine,
        mailer=None,  # type: ignore[arg-type]
        extend_lease=lambda: True,
    )


def embed_all(
    engine: Engine, settings: Settings, account: Account, provider: BagOfWords | None = None
) -> BagOfWords:
    provider = provider or BagOfWords()
    run_embed(
        embed_ctx(engine, configured(settings), account),
        provider_factory=lambda: provider,
        configured=True,
    )  # type: ignore[arg-type]
    return provider


def seed(account: Account) -> dict[str, str]:
    return {
        "project": add(account, "project", {
            "name": "Delivery delay report",
            "description": "Plotly dashboard for operations leads.",
            "technologies": ["Python", "SQL"],
        }),
        "intern": add(account, "internship", {
            "company": "Kestrel Analytics", "title": "Data Intern",
            "highlights": ["Cleaned six CSV sources with pandas", "Wrote SQL joins over 1.2 million rows"],
        }),
        "skill": add(account, "skill", {"name": "Python", "category": "Languages"}),
        "cert": add(account, "certification", {"name": "Machine learning basics", "issuer": "Example Learning"}),
    }  # fmt: skip


# ------------------------------------------------------------------ schema facts


def test_the_table_has_the_planned_shape_and_indexes(engine: Engine) -> None:
    with Session(engine) as db:
        column = db.execute(
            text(
                "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                "WHERE a.attrelid = 'evidence_chunks'::regclass AND a.attname = 'embedding'"
            )
        ).scalar_one()
        generated = db.execute(
            text(
                "SELECT attgenerated FROM pg_attribute WHERE attrelid = 'evidence_chunks'::regclass "
                "AND attname = 'tsv'"
            )
        ).scalar_one()
        indexes = {
            r.indexname: r.indexdef
            for r in db.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'evidence_chunks'"
                )
            )
        }
        forced = db.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'evidence_chunks'"
            )
        ).one()
    assert column == "vector(768)"
    assert generated == "s"  # a stored generated column
    assert "USING gin (tsv)" in indexes["evidence_chunks_tsv_idx"]
    assert "USING hnsw (embedding vector_cosine_ops)" in indexes["evidence_chunks_embedding_idx"]
    assert "UNIQUE" in indexes["evidence_chunks_source_uniq"]
    assert tuple(forced) == (True, True)


def test_the_database_refuses_inconsistent_chunks(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    entry = add(account, "skill", {"name": "Python"})
    uid = uuid.UUID(account.user_id)
    base = (
        "INSERT INTO evidence_chunks (owner_user_id, source_type, source_record_id, text, "
        "content_hash{cols}) VALUES (:o, 'profile_entry', :s, 'x', :h{vals})"
    )
    cases = {
        "two chunks for one source": (base.format(cols="", vals=""), entry),
        "a vector without its model name": (
            base.format(
                cols=", embedding", vals=", CAST(array_fill(0.1::real, ARRAY[768]) AS vector)"
            ),
            str(uuid.uuid4()),
        ),
        "a model name without a vector": (
            base.format(cols=", embedding_model", vals=", 'm'"),
            str(uuid.uuid4()),
        ),
        "a vector of the wrong size": (
            base.format(cols=", embedding, embedding_model", vals=", '[1,2,3]', 'm'"),
            str(uuid.uuid4()),
        ),
    }
    for name, (sql, source) in cases.items():
        with pytest.raises(DBAPIError), tenant_session(engine, uid) as db:
            db.execute(text(sql), {"o": uid, "s": source, "h": "0" * 64})
        assert name  # each case stands on its own: one failing statement per transaction


def test_row_level_security_hides_chunks_and_blocks_writing_for_someone_else(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    owner, other = make_account(app), make_account(app)
    add(owner, "skill", {"name": "Python"})

    def visible(user_id: str | None) -> int:
        with engine.connect() as conn, conn.begin():
            if user_id is not None:
                conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": user_id})
            return int(conn.execute(text("SELECT count(*) FROM evidence_chunks")).scalar_one())

    assert visible(owner.user_id) == 1
    assert visible(other.user_id) == 0
    assert visible(None) == 0  # no tenant set: fail closed
    with pytest.raises(DBAPIError), tenant_session(engine, uuid.UUID(other.user_id)) as db:
        db.execute(
            text(
                "INSERT INTO evidence_chunks (owner_user_id, source_type, source_record_id, text, content_hash) "
                "VALUES (:o, 'profile_entry', :s, 'forged', :h)"
            ),
            {"o": owner.user_id, "s": uuid.uuid4(), "h": "0" * 64},
        )


# ------------------------------------------------------------------ keeping chunks in step


def test_chunks_follow_entries_in_the_same_request_and_one_embedding_task_is_queued(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    ids = seed(account)
    assert chunk_texts(engine, account) == sorted(
        [
            "Certification: Machine learning basics, issued by Example Learning",
            "Internship: Data Intern at Kestrel Analytics. Cleaned six CSV sources with pandas; "
            "Wrote SQL joins over 1.2 million rows",
            "Project: Delivery delay report. Plotly dashboard for operations leads. Technologies: Python, SQL.",
            "Skill: Python (Languages)",
        ]
    )
    assert len(ids) == 4
    with Session(engine) as db:
        queued = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE task_type = 'embed_evidence' AND owner_user_id = :u "
                "AND state = 'queued'"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert queued == 1  # four quick edits, one waiting task: it reads the latest state when it runs


def test_editing_an_entry_updates_its_text_and_drops_the_now_wrong_vector(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    skill = add(account, "skill", {"name": "Python"})
    embed_all(engine, settings, account)
    assert rows(engine, account, "SELECT embedding IS NOT NULL AS has FROM evidence_chunks")[0].has

    patched = account.client.patch(
        f"{ENTRIES}/{skill}", json={"data": {"name": "Rust"}}, headers=account.csrf
    )
    assert patched.status_code == 200
    row = rows(
        engine,
        account,
        "SELECT text, embedding IS NULL AS gone, embedding_model FROM evidence_chunks",
    )[0]
    assert row.text == "Skill: Rust"
    assert row.gone is True and row.embedding_model is None


def test_deleting_an_entry_deletes_its_chunk_even_for_raw_sql(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    a, b = add(account, "skill", {"name": "Python"}), add(account, "skill", {"name": "Rust"})
    assert account.client.delete(f"{ENTRIES}/{a}", headers=account.csrf).status_code == 204
    assert chunk_texts(engine, account) == ["Skill: Rust"]
    with tenant_session(engine, uuid.UUID(account.user_id)) as db:
        db.execute(
            text("DELETE FROM profile_entries WHERE id = :id"), {"id": b}
        )  # the trigger does it
    assert chunk_texts(engine, account) == []


def test_reconcile_is_idempotent_and_heals_drift(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    seed(account)
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        assert not reconcile_profile_chunks(db, uid).changed
        db.execute(text("DELETE FROM evidence_chunks WHERE text LIKE 'Skill:%'"))
        db.execute(
            text(
                "INSERT INTO evidence_chunks (owner_user_id, source_type, source_record_id, text, content_hash) "
                "VALUES (:o, 'profile_entry', :s, 'orphan text', :h)"
            ),
            {"o": uid, "s": uuid.uuid4(), "h": "0" * 64},
        )
        healed = reconcile_profile_chunks(db, uid)
    assert (healed.created, healed.removed) == (1, 1)
    assert len(chunk_texts(engine, account)) == 4


def test_one_persons_profile_never_creates_chunks_for_another(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    a, b = make_account(app), make_account(app)
    add(a, "skill", {"name": "Python"})
    assert chunk_texts(engine, b) == []


# ------------------------------------------------------------------ the embedding task


def test_embedding_fills_every_chunk_records_each_call_and_stores_no_text_in_the_ledger(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    provider = embed_all(engine, settings, account)
    assert len(provider.calls) == 4
    status = rows(
        engine, account, "SELECT count(*) AS n, count(embedding) AS e FROM evidence_chunks"
    )[0]
    assert (status.n, status.e) == (4, 4)
    with Session(engine) as db:
        ledger = db.execute(
            text(
                "SELECT purpose, model, status, content_hash, input_tokens FROM llm_calls WHERE user_id = :u "
                "AND purpose = 'evidence_embedding'"
            ),
            {"u": account.user_id},
        ).all()
    assert len(ledger) == 4
    assert {r.model for r in ledger} == {MODEL} and {r.status for r in ledger} == {"ok"}
    assert all(r.content_hash and len(r.content_hash) == 64 for r in ledger)


def test_running_the_embedding_task_again_does_no_work(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    second = embed_all(engine, settings, account)
    assert second.calls == []


def test_only_the_changed_chunk_is_embedded_again(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    ids = seed(account)
    embed_all(engine, settings, account)
    account.client.patch(
        f"{ENTRIES}/{ids['skill']}", json={"data": {"name": "Go"}}, headers=account.csrf
    )
    again = embed_all(engine, settings, account)
    assert again.calls == ["Skill: Go"]


def test_a_model_change_marks_every_vector_as_stale(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        assert pending_embeddings(db, uid, "another-model", 50) != []
        assert evidence_status(db, uid, "another-model").embedded == 0
        assert evidence_status(db, uid, MODEL).embedded == 4


def test_without_a_key_the_task_succeeds_and_does_nothing_but_keep_chunks_in_step(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:  # simulate a profile that predates evidence search
        db.execute(text("DELETE FROM evidence_chunks"))
    provider = BagOfWords()
    run_embed(
        embed_ctx(engine, settings, account), provider_factory=lambda: provider, configured=False
    )  # type: ignore[arg-type]
    assert provider.calls == []
    assert len(chunk_texts(engine, account)) == 4  # the task still rebuilt the missing chunks


def test_a_busy_provider_keeps_the_progress_made_and_asks_for_a_retry(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    provider = BagOfWords(fail=LLMError("busy", retryable=True), fail_after=2)
    with pytest.raises(TaskFailure) as caught:
        embed_all(engine, settings, account, provider)
    assert caught.value.retryable is True
    assert rows(engine, account, "SELECT count(embedding) AS e FROM evidence_chunks")[0].e == 2
    embed_all(engine, settings, account)  # the retry only does the rest
    assert rows(engine, account, "SELECT count(embedding) AS e FROM evidence_chunks")[0].e == 4
    with Session(engine) as db:
        failed = db.execute(
            text(
                "SELECT count(*) FROM llm_calls WHERE user_id = :u AND purpose = 'evidence_embedding' "
                "AND status = 'error'"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert failed == 1


def test_a_rejected_request_is_not_retried(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    add(account, "skill", {"name": "Python"})
    with pytest.raises(TaskFailure) as caught:
        embed_all(engine, settings, account, BagOfWords(fail=LLMError("bad key", retryable=False)))
    assert caught.value.retryable is False


def test_a_model_with_the_wrong_vector_size_stores_nothing_and_says_why(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    add(account, "skill", {"name": "Python"})
    with pytest.raises(TaskFailure) as caught:
        embed_all(engine, settings, account, BagOfWords(size=256))
    assert caught.value.retryable is False
    assert "768" in str(caught.value) and "256" in str(caught.value)
    assert rows(engine, account, "SELECT count(embedding) AS e FROM evidence_chunks")[0].e == 0


def test_a_stale_vector_is_not_stored_when_the_text_changed_meanwhile(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    skill = add(account, "skill", {"name": "Python"})
    uid = uuid.UUID(account.user_id)
    with tenant_session(engine, uid) as db:
        ((chunk_id, _, old_hash),) = pending_embeddings(db, uid, MODEL, 5)
    account.client.patch(
        f"{ENTRIES}/{skill}", json={"data": {"name": "Rust"}}, headers=account.csrf
    )
    with tenant_session(engine, uid) as db:
        assert store_embedding(db, uid, chunk_id, old_hash, [0.1] * 768, MODEL) is False
    assert rows(engine, account, "SELECT count(embedding) AS e FROM evidence_chunks")[0].e == 0


def test_the_task_for_one_person_never_touches_another_persons_chunks(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    a, b = make_account(app), make_account(app)
    add(a, "skill", {"name": "Python"})
    add(b, "skill", {"name": "Rust"})
    provider = embed_all(engine, settings, a)
    assert provider.calls == ["Skill: Python"]
    assert rows(engine, b, "SELECT count(embedding) AS e FROM evidence_chunks")[0].e == 0


# ------------------------------------------------------------------ searching


def search(account: Account, query: str, **extra: Any) -> Any:
    return account.client.post(
        "/api/v1/evidence/search", json={"query": query, **extra}, headers=account.csrf
    )


def test_keyword_search_finds_words_stems_phrases_and_exclusions(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    seed(account)

    def found(query: str) -> list[str]:
        response = search(account, query)
        assert response.status_code == 200, response.text
        return [hit["entry_type"] for hit in response.json()["hits"]]

    assert found("pandas") == ["internship"]
    assert found("cleaning") == ["internship"]  # "Cleaned" in the text: English stemming
    assert found('"operations leads"') == ["project"]
    assert set(found("python")) == {"project", "skill"}
    assert found("python -sql") == ["skill"]  # minus removes entries that mention sql
    assert set(found("pandas OR certification")) == {"internship", "certification"}
    assert found("blockchain") == []


def test_hostile_or_broken_queries_are_just_text(app: FastAPI, make_account: MakeAccount) -> None:
    account = make_account(app)
    seed(account)
    for query in [
        "'; DROP TABLE evidence_chunks; --",
        '"unbalanced',
        "((",
        "a & b | !",
        "\\",
        "%",
        "😀",
    ]:
        assert search(account, query).status_code == 200, query
    assert account.client.get("/api/v1/evidence/status").json()["indexed"] == 4


def test_search_only_ever_sees_the_callers_own_evidence(
    app: FastAPI, make_account: MakeAccount
) -> None:
    a, b = make_account(app), make_account(app)
    add(a, "skill", {"name": "Quantum chromodynamics"})
    assert search(b, "chromodynamics").json()["hits"] == []
    assert len(search(a, "chromodynamics").json()["hits"]) == 1


def test_the_search_response_has_no_vectors_and_links_back_to_the_entry(
    app: FastAPI, make_account: MakeAccount
) -> None:
    account = make_account(app)
    skill = add(account, "skill", {"name": "Python"})
    body = search(account, "python").json()
    hit = body["hits"][0]
    assert hit["entry_id"] == skill
    assert (
        hit["matched_by"] == ["keyword"]
        and hit["keyword_rank"] == 1
        and hit["meaning_rank"] is None
    )
    assert set(hit) == {
        "chunk_id", "entry_id", "source_type", "entry_type", "text", "score",
        "matched_by", "keyword_rank", "meaning_rank", "similarity",
    }  # fmt: skip
    assert body["meaning_search_used"] is False and "needs an AI key" in body["note"]


def test_search_validates_and_is_protected(
    app: FastAPI, make_account: MakeAccount, build_app: Callable[..., FastAPI]
) -> None:
    account = make_account(app)
    for payload in (
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 301},
        {"query": "a", "limit": 0},
        {"query": "a", "limit": 21},
    ):
        assert (
            account.client.post(
                "/api/v1/evidence/search", json=payload, headers=account.csrf
            ).status_code
            == 422
        )
    assert account.client.post("/api/v1/evidence/search", json={"query": "a"}).status_code == 403
    assert new_client(app).post("/api/v1/evidence/search", json={"query": "a"}).status_code in (
        401,
        403,
    )
    assert new_client(app).get("/api/v1/evidence/status").status_code == 401

    policies = generous_policies()
    policies["evidence_search_user"] = RatePolicy("evidence_search_user", 2, 60)
    limited_app = build_app(policies=policies)
    other = make_account(limited_app)
    assert [search(other, "a").status_code for _ in range(3)] == [200, 200, 429]


def test_status_counts_chunks_and_says_whether_meaning_search_is_set_up(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    body = account.client.get("/api/v1/evidence/status").json()
    assert body == {"indexed": 4, "embedded": 0, "pending": 4, "meaning_search_configured": False}


def test_meaning_search_ranks_by_vector_similarity_and_ignores_other_models(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    cfg = configured(settings)
    outcome = hybrid_search(
        engine, cfg, uuid.UUID(account.user_id), "dashboard for operations", provider=BagOfWords()
    )  # type: ignore[arg-type]
    assert outcome.semantic_used and outcome.note is None
    top = outcome.hits[0]
    assert top.entry_type == "project"
    assert top.similarity is not None and 0.0 < top.similarity <= 1.0
    assert "meaning" in top.matched_by

    other_model = cfg.model_copy(update={"llm_embedding_model": "different-model"})
    note = hybrid_search(
        engine, other_model, uuid.UUID(account.user_id), "dashboard", provider=BagOfWords()
    )  # type: ignore[arg-type]
    assert not note.semantic_used and "not indexed" in (note.note or "")


def test_hybrid_ranks_an_entry_found_by_both_searches_above_one_found_by_one(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    outcome = hybrid_search(
        engine,
        configured(settings),
        uuid.UUID(account.user_id),
        "python sql dashboard",
        provider=BagOfWords(),  # type: ignore[arg-type]
    )
    first = outcome.hits[0]
    assert first.entry_type == "project"
    assert set(first.matched_by) == {"keyword", "meaning"}
    assert first.keyword_rank == 1 or first.meaning_rank == 1
    scores = [hit.score for hit in outcome.hits]
    assert scores == sorted(scores, reverse=True)
    assert first.score == pytest.approx(
        sum(1 / (60 + r) for r in (first.keyword_rank, first.meaning_rank) if r is not None)
    )


def test_meaning_search_finds_entries_that_keyword_search_cannot_combine(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    uid = uuid.UUID(account.user_id)
    # Keyword search needs every word in one entry, and no entry has both of these.
    assert search(account, "pandas dashboard").json()["hits"] == []
    outcome = hybrid_search(
        engine,
        configured(settings),
        uid,
        "pandas dashboard",
        provider=BagOfWords(),  # type: ignore[arg-type]
    )
    by_type = {hit.entry_type: hit for hit in outcome.hits}
    assert {"internship", "project"} <= set(by_type)
    assert by_type["internship"].matched_by == ("meaning",)
    assert by_type["project"].matched_by == ("meaning",)


def test_a_provider_outage_degrades_to_keyword_results_with_a_note(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    down = BagOfWords(fail=LLMError("down", retryable=True))
    outcome = hybrid_search(
        engine, configured(settings), uuid.UUID(account.user_id), "pandas", provider=down
    )  # type: ignore[arg-type]
    assert [h.entry_type for h in outcome.hits] == ["internship"]
    assert not outcome.semantic_used and "unavailable" in (outcome.note or "")
    with Session(engine) as db:
        errors = db.execute(
            text(
                "SELECT count(*) FROM llm_calls WHERE user_id = :u AND purpose = 'evidence_query' AND status = 'error'"
            ),
            {"u": account.user_id},
        ).scalar_one()
    assert errors == 1


def test_the_query_embedding_is_recorded_without_the_query_text(
    app: FastAPI, make_account: MakeAccount, engine: Engine, settings: Settings
) -> None:
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    hybrid_search(
        engine,
        configured(settings),
        uuid.UUID(account.user_id),
        "secret salary question",
        provider=BagOfWords(),
    )  # type: ignore[arg-type]
    with Session(engine) as db:
        row = db.execute(
            text(
                "SELECT content_hash, row_to_json(llm_calls)::text AS everything FROM llm_calls "
                "WHERE user_id = :u AND purpose = 'evidence_query'"
            ),
            {"u": account.user_id},
        ).one()
    assert len(row.content_hash) == 64
    assert "secret salary" not in row.everything


def test_the_api_uses_meaning_search_when_configured(
    build_app: Callable[..., FastAPI],
    make_account: MakeAccount,
    engine: Engine,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    storage: Any,
) -> None:
    app = build_app(
        storage=storage, gemini_api_key=SecretStr("test-key"), llm_embedding_model=MODEL
    )
    account = make_account(app)
    seed(account)
    embed_all(engine, settings, account)
    monkeypatch.setattr("pv_llm.evidence.build_provider", lambda *_a, **_k: BagOfWords())
    status = account.client.get("/api/v1/evidence/status").json()
    assert status == {"indexed": 4, "embedded": 4, "pending": 0, "meaning_search_configured": True}
    body = search(account, "dashboard for operations leads").json()
    assert body["meaning_search_used"] is True and body["note"] is None
    assert body["hits"][0]["entry_type"] == "project"
    assert "meaning" in body["hits"][0]["matched_by"] and body["hits"][0]["similarity"] > 0


def test_sync_evidence_queues_work_only_when_something_changed(
    app: FastAPI, make_account: MakeAccount, engine: Engine
) -> None:
    account = make_account(app)
    add(account, "skill", {"name": "Python"})
    uid = uuid.UUID(account.user_id)
    with Session(engine) as db, db.begin():
        db.execute(
            text("DELETE FROM tasks WHERE owner_user_id = :u AND task_type = 'embed_evidence'"),
            {"u": uid},
        )
    with tenant_session(engine, uid) as db:
        assert not sync_evidence(db, uid).changed
    with Session(engine) as db:
        count = db.execute(
            text(
                "SELECT count(*) FROM tasks WHERE owner_user_id = :u AND task_type = 'embed_evidence'"
            ),
            {"u": uid},
        ).scalar_one()
    assert count == 0
