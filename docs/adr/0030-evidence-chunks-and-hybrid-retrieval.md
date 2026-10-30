# ADR-0030: Evidence chunks and hybrid retrieval

Status: Accepted (checkpoint 1.7). Builds on [ADR-0003](0003-pgvector-instead-of-a-separate-vector-database.md), [ADR-0011](0011-evidence-grounded-matching.md), [ADR-0015](0015-postgres-rls-as-defense-in-depth.md) and [ADR-0029](0029-resume-storage-parsing-and-profile-entries.md).

## Context
From checkpoint 1.9 the evidence agent must find proof in a person's profile for each requirement of a job. That needs a search over the profile that finds exact words (names, tools, numbers) and also finds entries that say the same thing in other words. It must be private per user, must not silently use stale data, and must keep working when the AI provider is unavailable or not configured.

## Problem
What is the unit of search, where is it stored, how is it kept correct, and how do keyword and meaning search combine?

## Options considered
| Question | Options | Result |
|---|---|---|
| Unit of search | split every entry into small pieces, one chunk per entry | One chunk per entry. Entries are already short and meaningful, and a verdict later cites an entry, so a one-to-one mapping keeps citations simple. Revisit when long documents (GitHub READMEs, 3.1) arrive |
| Storage | separate vector service, pgvector in the same database | pgvector in PostgreSQL (ADR-0003). One system, one transaction, Row Level Security applies |
| Keeping chunks correct | recompute on a schedule, in each write path, database triggers for everything | Chunks are rebuilt by one idempotent function (`reconcile_profile_chunks`) called in the same transaction as every profile change. A database trigger covers deletes so removing an entry always removes the text derived from it, whatever code deleted it |
| Embedding | in the request, in a worker | In a worker task. A chunk whose text changed loses its vector immediately, so a stale vector can never answer a search |
| Keyword search | `ILIKE`, trigram, full text | Full text with a generated `tsvector` (English stemming) and `websearch_to_tsquery`, which accepts plain words, quoted phrases, `OR` and a minus sign and never raises on odd input |
| Meaning search | exact scan, HNSW, IVFFlat | HNSW with cosine distance. Vectors from another model are ignored because they are not comparable |
| Combining | weighted sum of scores, rank fusion | Reciprocal rank fusion with k = 60. Only ranks matter, so a text rank and a cosine distance never have to share a scale, and no weight has to be tuned without data |
| No key or no vectors | fail the search, degrade | Degrade: return keyword results with a plain note saying meaning search is off, not indexed, or unavailable. A search never fails because the AI does |
| Vector size | configurable, fixed | Fixed at 768 by the migration. Changing it needs a migration and re-embedding everything. The worker refuses a model that answers with another size |

## Decision
1. **Table.** `evidence_chunks` (tenant data, RLS enabled and forced): `source_type` (`profile_entry` now, `user_answer` from 1.9), `source_record_id`, the rendered `text`, `content_hash`, nullable `embedding vector(768)` with its `embedding_model`, a generated `tsv`. Unique on (owner, source type, source record). A check ties the vector and its model name together.
2. **Text.** `pv_domain.evidence.render_entry_text` writes a short deterministic sentence per entry type. The hash of that text says whether the vector is stale.
3. **Sync.** `sync_evidence` runs after every entry create, update and delete (API) and after a resume parse saves entries (worker), in the same transaction. If anything changed it queues one embedding task unless one is already waiting.
4. **Embedding task.** `embed_evidence` first reconciles (so profiles that predate this feature are filled in), then embeds chunks that have no vector or a vector from another model. It stores a vector only if the chunk still has the text it was computed from. It keeps its progress when a call fails. With no key it succeeds and does nothing. Every call is recorded in `llm_calls` with a content hash and never the text. `python -m pv_worker.cli reindex-evidence` (or `.\scripts\pv.ps1 embeddings`) queues the task for everyone after a key or model change.
5. **Search.** `pv_llm.evidence.hybrid_search` runs keyword search always, embeds the query and runs meaning search when configured and indexed, then fuses the two ranked lists. Each hit says how it was found (keyword, meaning, both), its ranks and its similarity. Only chunk ids and text leave the database, never vectors.
6. **API.** `GET /api/v1/evidence/status` (counts and whether meaning search is configured) and `POST /api/v1/evidence/search` (CSRF protected, rate limited, query capped at 300 characters). The profile screen has a search box so a person can see what a job would find.
7. **Relevance floor.** `EVIDENCE_MIN_SIMILARITY` (default 0, off) can drop weak meaning matches. It is set from labeled data in checkpoint 3.6, not guessed.

## Why
One transaction keeps keyword search always current and makes "delete means delete" true by construction. Rank fusion avoids inventing weights before there is data. Degrading instead of failing keeps the product honest and usable on the free tier with no key.

## Consequences
- Chunk text is sent to the model provider to be embedded, and the search query is sent when meaning search is used. On a free tier that text may be used for training, so only the owner's own data until a paid tier with no-training terms (ADR-0027).
- Meaning search quality depends on the embedding model. A model change re-embeds everything (cost, and `reindex-evidence`).
- `websearch_to_tsquery` requires every word to appear in one entry. That is why meaning search matters for questions that span words from different entries.
- Matching is deterministic but not an explanation: a hit says "found by meaning", not why. Explanations come from the agent in 1.9, which must still cite the text.
- With many entries per user the HNSW index is overkill but harmless. With the planned scale (tens of entries per user) the owner filter does the work.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Everything in one database. Embedding runs in seconds per profile |
| 100 | Same. Provider rate limits shape embedding time (`LLM_MIN_INTERVAL_SECONDS`) |
| 10,000 | Per-owner filtering keeps queries small. Embedding cost is per changed chunk, tracked in the ledger. Consider a quota per user (3.3) |

## Revisit when
Entries get long enough to need splitting, meaning search quality is measured poorly in the evaluation set (3.6), the vector size must change, or a second text source (answers, GitHub) joins the table.
