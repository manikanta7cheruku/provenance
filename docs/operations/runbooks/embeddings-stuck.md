# Runbook: Meaning search is empty, stale or stuck

Keyword search needs only the database. Meaning search needs vectors, which the worker makes with the embedding model. Users see "Meaning search is off until an AI key is set up", "still indexing: 2 of 5 done", or no meaning matches at all.

## Detection
- The Profile screen's search status line.
- `GET /api/v1/evidence/status` for a user: `indexed`, `embedded`, `pending`, `meaning_search_configured`.
- Admin, System: the queue shows `embed_evidence` tasks. A growing count of waiting tasks or any dead letter of that type is the signal.

## Diagnosis
1. `meaning_search_configured` false: `GEMINI_API_KEY` or `LLM_EMBEDDING_MODEL` is missing on the api or the worker. Check `.env`, then `docker compose exec api printenv GEMINI_BASE_URL` (a wrong URL fails every call). Run `.\scripts\pv.ps1 ai-check`.
2. Configured but `pending` stays above zero: look at the task. `.\scripts\pv.ps1 queue`, then worker logs: `.\scripts\pv.ps1 logs worker`.
   - `429` or "busy": the provider rate limit. Set `LLM_MIN_INTERVAL_SECONDS` (for example 4 on a free tier). The task retries with backoff and keeps its progress.
   - "returned N numbers but the database stores 768": the embedding model answers with another size. Pick a model that supports 768 dimensions, or plan a migration. Nothing was stored.
   - "bad key" style errors are not retried and dead-letter after one attempt. Fix the key, then requeue.
3. Embedded but search finds nothing by meaning: the vectors came from another model. `pending` counts them. A model change needs `reindex-evidence`.
4. Check the ledger for cost and errors (no text is stored): `SELECT status, count(*) FROM llm_calls WHERE purpose IN ('evidence_embedding','evidence_query') GROUP BY 1;`

## Mitigation
- Keyword search keeps working for everyone. Tell users that matches may be fewer until indexing finishes.
- Never edit `evidence_chunks` by hand. The text is derived and the next change or `reindex-evidence` rebuilds it.

## Recovery
- After fixing configuration: `.\scripts\pv.ps1 restart worker`, then `.\scripts\pv.ps1 embeddings` (queues one task per active user). It only embeds what is missing, so it is safe to repeat.
- A dead-lettered `embed_evidence` task can be requeued from Admin, System. It holds no secret.

## Prevention
- Run `python -m pv_llm.check` after any key or model change.
- Record the embedding model name in the change notes: it decides which vectors are valid.
- Do not paste entry text into tickets. Use the user id and the chunk counts.
