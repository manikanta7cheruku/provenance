# Checkpoint 1.8: Paste a job, extract requirements, check eligibility

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.8-job-extraction-eligibility`. Decisions: [ADR-0031](../adr/0031-job-paste-extraction-and-eligibility.md). Runbook: [a pasted job could not be read](../operations/runbooks/job-reading-failed.md).

A person pastes a job description. The product reads what it asks for, quotes the posting for every claim, and says whether anything stands in their way. It does not score a match yet. That is 1.9.

## 1. Build

**Database (migration 0006, literal SQL).** `job_postings` and `job_requirements`, both with Row Level Security enabled and forced. A job is unique per owner by content hash. `source_name` and `acquisition_method` are separate columns.

**Domain.** `job.py` (limits, source labels, vocabularies, error codes and messages, text cleaning, content hash, `find_quote`), `experience.py` (years of experience from profile dates, overlaps counted once, unknown is not zero), `job_facts.py` (grounding of model output), `eligibility.py` (five gates, four states, rules version `eligibility-1`), `JobUiState` in `states.py`, a task name and two rate limits.

**Persistence.** `pv_persistence.jobs`: read and list, start extraction (run plus idempotent task keyed by generation), save, mark failed, cancel waiting tasks, load the seeker's preferences and years.

**Model layer.** `pv_llm.job_extract`: schemas, prompt `job-extract-1` with a nonce-delimited posting, `extract_job_text`.

**Worker.** `extract_job` with steps read, extract, check quotes, save. Visible failures: `AI_NOT_CONFIGURED`, `AI_UNAVAILABLE`, `AI_BAD_OUTPUT`, `NO_REQUIREMENTS`. Only transient provider failures retry.

**API.** `POST/GET /api/v1/jobs`, `GET/DELETE /jobs/{id}`, `POST /jobs/{id}/reanalyze`. Duplicate paste returns the existing job. Eligibility is computed on read.

**Web.** `/opportunities` (paste form and list) and `/opportunities/:jobId` (state, gates with the posting's words, stated facts, requirements grouped required and nice to have, the pasted text, read again, delete with confirmation). Shared state vocabularies are checked against the backend.

## 2. UX

- One text box. A source label and an optional link. No account on other sites is needed.
- The detail page leads with the answer to "can you take this job?", each gate with a reason and a quote. A gate that needs your answer links to the profile.
- When suggestions were left out because the posting did not contain them, the page says how many.
- Failures say what happened and what to do, and the text is never lost.

## 3. Technical acceptance criteria

1. Migration 0006 applies after 0005 and reverses. Row Level Security is enabled and forced. Other tenants and no tenant see nothing, and a forged insert is refused.
2. Every stored requirement and fact has a quote found in the posting. Fabricated quotes and values are dropped and counted.
3. Smart quotes, long dashes, mixed case, extra spaces and Hinglish text are handled. Regex characters in a quote are plain text.
4. The same posting (any spacing or case) is not stored twice. Re-analysis is explicit and returns 409 while a reading is running.
5. A missing key, an outage, bad output and an empty result each show the right plain message. Only transient failures retry.
6. Eligibility gives the same answer for the same facts and preferences, orders gates worst first, and a blocker is never hidden by good news.
7. A different person's job is 404. Rate limits and CSRF apply. Audit events never contain the text.
8. Ruff, mypy, import-linter, unit and integration tests pass. Web checks (copy, tokens, contrast, states, boundaries) pass.

## 4. UX acceptance criteria

1. A short paste is explained next to the field and focus moves to it.
2. Reading shows progress and updates by itself every two seconds.
3. Gates, facts and requirements always carry a label and a quote, never color alone.
4. Delete asks first and says what is removed.

## 5. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the jobs list (empty and filled) and the job detail while reading, ready and failed, in light and dark. The state line is a live region. Quotes are blockquotes with a visible label and rule.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_job_domain.py` | cleaning, hashing, quote finding, states, experience years |
| `tests/unit/test_eligibility.py` | every gate and state, ordering, versioning |
| `tests/unit/test_job_extraction.py` | ten fixtures through the model layer with a scripted provider, including an obeyed injection and fabricated quotes |
| `tests/integration/test_jobs.py` | schema, Row Level Security, API, dedupe, re-analysis, deletion, worker handler, audit, rate limit |
| `src/features/opportunities/opportunities.test.tsx` | labels, state vocabularies, paste validation, detail rendering, retry, delete |
| `e2e/jobs.spec.ts` | axe in both themes for each state, paste flow, duplicate notice, retry and delete, not found |

## 7. Document

[ADR-0031](../adr/0031-job-paste-extraction-and-eligibility.md), [data-model.md](../architecture/data-model.md), [llm-provider-gemini.md](../operations/llm-provider-gemini.md), the [runbook](../operations/runbooks/job-reading-failed.md) and index, [product-requirements.md](../product/product-requirements.md), the roadmap status.

## 8. Commit

```
feat(jobs): add job paste, requirement extraction with quotes and eligibility gates
```

## 9. Interview defense

You should be able to explain:
- Why the model only proposes and code decides what is kept (grounding), and what grounding cannot prove.
- Why eligibility is deterministic, versioned and computed on read.
- Why only transient failures retry and every other failure is a visible result.
- How a content hash dedupes pastes, and how a generation counter makes tasks safe to repeat.
- Why `source_name` and `acquisition_method` are separate, and why we never fetch a pasted link.
- What an injected instruction can and cannot change.

## 10. What was verified and what was not

Verified: all tests listed above, a live run on the Docker stack (paste, duplicate, visible failure with no key, retry, delete, 404 afterwards), migration 0006 applied to the local database.

Not verified: a real model call. No Gemini key was configured here, so extraction quality on real postings is untested. The ten fixtures use a scripted provider. Set a key, run `.\scripts\pv.ps1 ai-check`, and paste three real postings to see it. Scoring and the trust screen arrive in 1.9.

## 11. Run it yourself

```
.\scripts\pv.ps1 up
```
Open `/opportunities`, set your preferences on `/profile`, paste a job. Without a key the page says the reading service is not set up.
