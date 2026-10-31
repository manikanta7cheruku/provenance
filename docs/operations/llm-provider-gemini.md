# Gemini provider (development, free tier)

Model names, embedding model, dimensions and prices are **configuration**. Nothing in the code names a model. Model lineups change often and older models are shut down, so you look names up from your own key instead of trusting this document or any article.

**Free tier warning.** Free-tier prompts may be used by the provider to improve its products. Use only your own test data. Real users require a paid tier with terms that exclude training. That is a launch gate (see `docs/product/business-model.md`).

## 1. Get a key
1. Open Google AI Studio and create an API key (use a project you do not mind being rate limited).
2. Put it in `.env`: `GEMINI_API_KEY=...`. Never commit `.env`.

## 2. Find the models your key can use
```powershell
.\scripts\pv.ps1 ai-check
```
Expected output (names will differ):
```
Models that support generateContent (N):
  <name>
  ...
Models that support embedContent (M):
  <name>
  ...

LLM_MODEL is not set. Pick a name from the first list and put it in .env.
```
The tool lists names only. It never prints your key. Exit code 2 means "not configured yet".

## 3. Choose and set the models
Edit `.env`:
```
LLM_MODEL=<a name from the generateContent list>
LLM_EMBEDDING_MODEL=<a name from the embedContent list>
LLM_EMBEDDING_DIMENSIONS=768
```
Run `.\scripts\pv.ps1 ai-check` again. Expected:
```
OK generation with <model>: 640 ms, 8 input tokens, 2 output tokens
OK embedding with <embedding model>: 768 dimensions
```
Restart the worker so it reads the new `.env`: `.\scripts\pv.ps1 restart worker`.

## 4. Change the model later
Edit `LLM_MODEL` in `.env`, run `ai-check`, restart the worker. Results store the model name per call (`llm_calls.model`), so history stays truthful.

## 5. Change the embedding model or dimensions
The embedding size is **fixed in the database** when checkpoint 1.7 creates the `vector(768)` column. To use a different size you need a migration and a re-embedding of every stored chunk. Do not change `LLM_EMBEDDING_DIMENSIONS` alone: `ai-check` will fail if the model returns a different size than configured, which is the early warning.

## 6. Prices and cost
Cost is estimated, never invented. Copy the per-million-token prices from the provider's **official pricing page** into `.env`:
```
LLM_INPUT_PRICE_PER_MILLION=
LLM_OUTPUT_PRICE_PER_MILLION=
LLM_EMBEDDING_PRICE_PER_MILLION=
```
They default to `0`, so cost shows as `$0` until you set them. Free tier usage is also `$0` in reality. Check the page again before launch: prices and tiers change.

## 7. Free-tier throttling
Free tiers limit requests per minute and per day. Set a minimum gap between calls:
```
LLM_MIN_INTERVAL_SECONDS=4
```
The provider sleeps so calls are at least that many seconds apart (per process). A rate-limit reply (HTTP 429) is classified as retryable, so the worker retries with backoff instead of failing the task. If you still hit limits, raise the interval or run one worker.

## 8. Failure behaviour
| Provider answer | Class | What happens |
|---|---|---|
| timeout, network error, 408, 429, 500, 502, 503, 504 | retryable | task retries with backoff |
| 400, 401, 403, 404, no candidate returned | permanent | task fails now, run shows an error |

Error text from the provider is never copied into logs or the database, because it can echo your input.

## 9. Switching providers
The rest of the system depends only on the `LLMProvider` protocol in `pv_llm.base` (`list_models`, `generate`, `embed`). To add a provider:
1. Add a class in `packages/llm/src/pv_llm/<provider>.py` that implements the protocol and raises `LLMError(retryable=...)`.
2. Add its settings (key, prices) to `pv_config.Settings` and `.env.example`.
3. Select the provider where the first feature calls it (checkpoint 1.6 adds the single factory function). Keep model names in configuration.
4. Record every call with `pv_llm.record_result`, so cost and usage stay comparable.
5. Add a unit test with `httpx.MockTransport` like `tests/unit/test_llm.py`, and write an ADR.

## 10. What was checked
The REST shapes used (base `v1beta`, `x-goog-api-key` header, `models.list` with `supportedGenerationMethods`, `generateContent`, `embedContent` with `outputDimensionality`, `usageMetadata` token counts) were checked against the official API reference on 2026-10-22. The unit tests use a mocked HTTP transport. **A live call has not been made**: run `ai-check` with your key to confirm.

## First feature using the model: resume parsing (checkpoint 1.6)

The worker task `parse_resume` makes one structured call per resume (and one guided retry if the answer does not match the schema). Each call is recorded in `llm_calls` with purpose `resume_parse`, the prompt version (`resume-parse-1`, in `pv_llm.resume_parse`) and a content hash, never text. It needs `GEMINI_API_KEY` and `LLM_MODEL`. Without them a parse ends as a visible, retryable failure with the message "The reading service is not set up yet", and nothing crashes or loops.

The whole resume text is sent to the provider. On a free tier that text may be used to improve the provider's products, so use only your own test data until a paid tier with no-training terms is in place (see [ADR-0027](../adr/0027-build-first-sequencing-and-paid-service-placeholders.md)).

## Embeddings and evidence search (checkpoint 1.7)

The worker task `embed_evidence` embeds one short text per profile entry with `LLM_EMBEDDING_MODEL`, and the API embeds each search query. Calls are recorded in `llm_calls` with purposes `evidence_embedding` and `evidence_query`, a content hash and never text. The evidence check (checkpoint 1.9) uses purpose `evidence_agent` with prompt version `evidence-agent-1`: one to four calls per requirement, up to 90 per job, so a free tier rate limit decides how long a job takes. Job reading (checkpoint 1.8) uses purpose `job_extraction` with prompt version `job-extract-1`: the pasted posting is sent to the model, so on a free tier only the owner's own jobs should be pasted. Meaning search needs both `GEMINI_API_KEY` and `LLM_EMBEDDING_MODEL`. Without them keyword search still works and the screen says meaning search is off.

The database stores vectors of exactly 768 numbers (migration 0005). `python -m pv_llm.check` tests one embedding with `LLM_EMBEDDING_DIMENSIONS` (default 768): choose a model that supports that size. A model that answers with another size makes the worker stop with a clear message and store nothing. Changing the model makes every stored vector stale. Run `.\scripts\pv.ps1 embeddings` to re-embed.

`GEMINI_BASE_URL` (default the official endpoint) is operator configuration for a proxy or a local test double. `EVIDENCE_MIN_SIMILARITY` (default 0) drops weak meaning matches. Leave it at 0 until the evaluation set (checkpoint 3.6) shows where the line belongs.

Entry text goes to the provider to be embedded. On a free tier it may be used for training, so use only your own data until a paid tier with no-training terms is in place (ADR-0027).

