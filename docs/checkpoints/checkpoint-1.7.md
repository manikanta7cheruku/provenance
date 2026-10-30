# Checkpoint 1.7: Evidence chunks, embeddings and hybrid retrieval

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.7-evidence-retrieval`. Decisions: [ADR-0030](../adr/0030-evidence-chunks-and-hybrid-retrieval.md). Runbook: [meaning search empty or stuck](../operations/runbooks/embeddings-stuck.md).

This checkpoint builds the search the evidence agent (1.9) will use to find proof in a person's profile. It finds candidate evidence. It does not decide whether a requirement is met.

## 1. Build

**Database (migration 0005, literal SQL).** `evidence_chunks`: one chunk per profile entry with the rendered `text`, a `content_hash`, a generated `tsvector` with a GIN index, a nullable `vector(768)` with its `embedding_model` and an HNSW index (cosine), unique on (owner, source type, source record), a check that ties a vector to its model name, Row Level Security enabled and forced. A trigger on `profile_entries` deletes the entry's chunk.

**Domain (`pv_domain.evidence`).** `render_entry_text` (a deterministic sentence per entry type), content hashing, query cleaning, the fixed vector size, and `reciprocal_rank_fusion` (k = 60, deterministic ties).

**Persistence (`pv_persistence.evidence`).** `reconcile_profile_chunks` (makes chunks match entries, idempotent, clears the vector of any chunk whose text changed), `sync_evidence` (called in the same transaction as every profile change, queues one embedding task unless one is waiting), `pending_embeddings`, `store_embedding` (only if the chunk still has the text it was computed from), `evidence_status`, `search_keyword` (`websearch_to_tsquery`, `ts_rank_cd`) and `search_meaning` (cosine distance, same model only).

**Model layer (`pv_llm`).** `hybrid_search`: keyword search always, query embedding and meaning search when configured and indexed, fusion of the two lists, and a plain note whenever meaning search is not used (no key, nothing indexed, provider unavailable). `build_provider(for_embeddings=True)` and `embeddings_configured`. The Gemini base URL is now configuration (`GEMINI_BASE_URL`).

**Worker (`embed_evidence`).** Reconciles the chunks, then embeds what is missing in batches, keeps progress when a call fails, extends its lease per call, records every call in `llm_calls` without text, refuses a model that answers with another vector size, and does nothing (successfully) with no key. After profile changes and resume parses, `sync_evidence` queues it. `python -m pv_worker.cli reindex-evidence` and `.\scripts\pv.ps1 embeddings` queue it for every active user.

**API.** `GET /api/v1/evidence/status` and `POST /api/v1/evidence/search` (CSRF, rate limited at 60 per hour per user, query 1 to 300 characters, limit 1 to 20). Responses contain text, how each hit was found, ranks and similarity, never vectors. The LLM settings now reach the api container as well as the worker.

**Web.** A "Search your evidence" section on `/profile`: a status line that says what the search can do right now (indexed count, meaning search off, indexing progress, ready), a search box, and results labelled "From your profile" with how each was found and a link to the entry. Notes from the server are shown as they are.

**Tools.** `scripts/fake_gemini.py` (a local stand-in for the embedding endpoint to try meaning search without a key) and the operator section that explains it.

## 2. UX

- A person can see what a job analysis will find: every requirement is looked up in their own entries, and they can try that here.
- The screen never overstates: it says plainly when meaning search is off, still indexing or unavailable, and results always say "From your profile".
- No entries means the search box is disabled and the status line says there is nothing to search yet.

## 3. Technical acceptance criteria

1. Migration 0005 applies after 0004 and reverses. The table has `vector(768)`, a stored generated `tsvector`, a GIN index, an HNSW cosine index, a unique source index and forced Row Level Security.
2. The database refuses a second chunk for one source, a vector without its model name, a model name without a vector, and a vector of the wrong size.
3. Other tenants and "no tenant" see no chunks, and a tenant cannot insert a chunk for someone else.
4. Chunks follow entry create, update and delete in the same request. Four quick edits queue one embedding task.
5. Editing an entry changes its text and clears its vector at once. Deleting an entry deletes its chunk even through raw SQL.
6. Reconcile is idempotent and heals drift (a missing chunk is recreated, an orphan is removed).
7. The embedding task embeds every chunk, records each call without text, does no work the second time, re-embeds only a changed chunk, treats another model's vectors as stale, keeps progress on a retryable failure, does not retry a rejected request, refuses a wrong vector size and stores nothing, never stores a stale vector, and never touches another person's chunks. With no key it succeeds and keeps the chunks in step.
8. Keyword search handles words, stems, quoted phrases, OR and a minus sign, and treats hostile input as text. It only ever returns the caller's own entries.
9. Meaning search ranks by vector similarity and ignores vectors from another model. Fusion puts an entry found by both searches first, and scores equal the fusion formula.
10. A provider outage, no key, or nothing indexed yields keyword results and a plain note, not an error. The query embedding call is recorded without the query text.
11. The search responses contain no vectors. Validation, CSRF, authentication and the rate limit are enforced.
12. Ruff, mypy, import-linter, unit tests, integration tests and the web checks pass. CI is green.

## 4. UX acceptance criteria

1. The status line, the "no matches" message and the notes use plain language and never claim meaning search ran when it did not.
2. An empty query is explained and focus moves to the field. Results are announced politely.
3. Each result says where it came from and how it was found, and links to the entry.

## 5. Accessibility acceptance criteria

1. Axe finds no WCAG 2.2 A or AA violation on the Profile page with search results and with no results, with meaning search on and off, in light and dark.
2. The search form has a visible label, a hint, a linked error, and works with the keyboard (Enter submits).
3. The results region is a polite live region. Results are an ordered list with a visible leading rule, not color alone.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_evidence_domain.py` | rendering of every entry type, hashing, query cleaning, rank fusion |
| `tests/unit/test_llm_factory.py` | provider configuration, embedding configuration, base URL |
| `tests/integration/test_evidence.py` | schema facts, constraints, Row Level Security, keeping chunks in step, the embedding task, keyword search, meaning search with a deterministic embedder on real pgvector, fusion, degradation, ledger, API |
| `tests/integration/test_resume_profile.py` | a parse indexes the entries it stores |
| `src/features/profile/evidence.test.tsx` | status wording, result labels, validation, states |
| `e2e/evidence.spec.ts` | axe with and without results and with meaning search on and off in both themes, the search flow, validation, the link to the entry, the empty profile |

## 7. Document

[ADR-0030](../adr/0030-evidence-chunks-and-hybrid-retrieval.md), [data-model.md](../architecture/data-model.md), [privacy.md](../compliance/privacy.md), [security-controls.md](../security/security-controls.md), [llm-provider-gemini.md](../operations/llm-provider-gemini.md), [operator-commands.md](../operations/operator-commands.md), the [embeddings runbook](../operations/runbooks/embeddings-stuck.md) and the runbook index, [product-requirements.md](../product/product-requirements.md) (FR-EVI-1), the roadmap status.

## 8. Commit

```
feat(evidence): add evidence chunks, embeddings and hybrid retrieval
```
Include the updated `uv.lock` (the api now depends on the `pv-llm` workspace package). No third-party dependency was added.

## 9. Interview defense

You should be able to explain:
- Why keyword and meaning search are combined, what each is good and bad at, and how rank fusion avoids tuning weights.
- How full-text search works in Postgres (tsvector, stemming, GIN, `websearch_to_tsquery`) and what an embedding and cosine distance are.
- How derived data is kept correct: same transaction, stale vectors cleared at once, store-only-if-unchanged, a delete trigger.
- Why embedding is a worker task and why that task is idempotent and keeps progress.
- How the search degrades and tells the user instead of failing.
- What goes to the provider, how it is recorded without text, and how tenant isolation is tested.
- How a vector search was tested without paying for a model, and what that does not prove.

## 10. What was verified and what was not

**Run in this checkpoint:** ruff, mypy (strict), import-linter; the Python unit tests (275 passed) and the full integration suite against the real PostgreSQL with pgvector in the Docker stack with the worker stopped (207 passed, 31 of them new); migration 0005 applied; the web checks, 55 web unit tests, the production build and 54 browser tests in Edge. **A live run on the Docker stack through the real Gemini REST client** against `scripts/fake_gemini.py`: four entries embedded by the worker, a hybrid search found the right project by keyword and by meaning, a "pandas dashboard" query found two entries by meaning only, an edit re-embedded exactly one chunk, and the ledger showed five embedding calls and two query calls with no text. The stack was then restored to its normal configuration.

**Not verified:** the quality of meaning search with a real embedding model (no key is configured), whether a real model supports 768 dimensions for the model you choose (use `ai-check`), the relevance floor (left at 0), large profiles, Firefox, Safari, screen readers, GitHub CI on the branch.

Likeliest first-CI problems: none expected from dependencies (none were added). If the integration job fails, check that the Postgres service image is the pgvector image so `CREATE EXTENSION vector` and the HNSW index work.

## 11. Run it yourself

```powershell
.\scripts\pv.ps1 up
```
Sign in, open Profile, add or keep a few entries, and try the search. To see meaning search with no real key, follow "Try meaning search without a real key" in [operator-commands.md](../operations/operator-commands.md). With your own key, run `.\scripts\pv.ps1 ai-check`, set `LLM_EMBEDDING_MODEL` in `.env` (a model that supports 768 dimensions), `.\scripts\pv.ps1 restart worker`, then `.\scripts\pv.ps1 embeddings`.
