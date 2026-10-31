# ADR-0031: Job paste, grounded requirement extraction and deterministic eligibility

Status: Accepted (checkpoint 1.8). Builds on [ADR-0006](0006-source-adapter-architecture.md), [ADR-0011](0011-evidence-grounded-matching.md), [ADR-0012](0012-prompt-injection-threat-model.md), [ADR-0015](0015-postgres-rls-as-defense-in-depth.md) and [ADR-0029](0029-resume-storage-parsing-and-profile-entries.md).

## Context
A person pastes a job description. The product has to turn free text into structured facts and requirements, say whether anything stands in their way, and never show a claim that is not in the posting. Job text is written by strangers, so it is untrusted input and may try to instruct the model.

## Problem
How do we read a posting with a model, trust none of what it says, and decide eligibility without letting the model decide?

## Options considered
| Question | Options | Result |
|---|---|---|
| How a job enters | scrape links, import files, paste | Paste only. We never visit a link the person gives us, so no site terms apply. `source_name` (a label) and `acquisition_method` (`user_paste`) are stored separately so later sources stay auditable |
| Who reads the text | rules only, model only, model plus checks | Model proposes, code checks. The model returns facts and requirements, each with a verbatim quote. Code keeps only what it can verify |
| What counts as verified | trust the model, check quotes, check quotes and values | A quote must be found in the posting (whitespace, case, quote marks and dashes forgiven). A fact value must also pass vocabulary and value checks. Years of experience must appear as a digit or number word inside the quote. Location tokens must appear in the posting. Title and company must be grounded token by token. Unverifiable items are dropped and counted, and the screen says how many |
| Eligibility | model decides, model score, deterministic gates | Five deterministic gates in code: work authorization and sponsorship, location and work mode, experience asked for, kind of work, things the person chose to avoid. Four states: eligible, not eligible, uncertain, requires user input. A blocker is stated as a blocker and never averaged into a score |
| When eligibility is computed | stored, on read | On read, from the stored facts and the person's current preferences and profile dates. Changing a preference changes the answer at once with no re-analysis. The rules version (`eligibility-1`) is returned with the result |
| Repeated pastes | analyse again, dedupe | Dedupe by content hash (whitespace collapsed, case folded) per owner. The same posting returns the existing record with `duplicate: true`. Re-analysis is an explicit action |
| Retries | retry everything, retry transient only | Only transient provider failures retry. A missing key, bad output and a posting with no requirements are visible results with a plain message and a "Read it again" action |
| Stale work | last writer wins, generation counter | `analysis_generation` is part of the task key. Re-analysis bumps it, so an old task cannot overwrite a newer result, and saving replaces the previous requirements |

## Decision
1. **Tables (migration 0006).** `job_postings` (private, `raw_text` 100 to 20,000 characters, `content_hash`, unique per owner, `facts` jsonb, `parse_status`, `analysis_generation`, `error_code`, drop counts, `prompt_version`, `run_id`) and `job_requirements` (ordinal, text, kind, category, `years_min`, `quote` with `quote_start` and `quote_end`). Row Level Security enabled and forced on both.
2. **Prompt.** `job-extract-1`. The posting is wrapped in nonce delimiters and the prompt says its content is data. Output is validated against a schema with one guided retry whose feedback names field paths and error kinds, never values.
3. **Grounding.** `pv_domain.job_facts.ground_extraction` is pure Python with no model access. It is the only path from model output to stored data.
4. **Eligibility.** `pv_domain.eligibility.evaluate_eligibility` is pure and versioned. Unknown is not zero: with no usable profile dates, the experience gate asks for input instead of assuming zero years.
5. **API.** `POST /api/v1/jobs` (201, or 200 for a duplicate), `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/reanalyze` (409 while reading), `DELETE /jobs/{id}`. Rate limits: 30 pastes and 20 re-analyses per hour per user. Audit events record ids, never the text. Other people's jobs are 404.
6. **Worker.** Task `extract_job`, steps read, extract, check quotes, save. Every model call goes to the `llm_calls` ledger without text.

## Why
The model is good at reading messy text and bad at being trusted. Splitting "propose" from "verify" keeps its strength and removes its weakness. Eligibility questions have right answers given facts, so they belong in tested code.

## Consequences
- Grounding proves a statement is present in the posting, not that it applies to the requirement the model says it supports. An injected sentence that is part of the pasted text can pass grounding as a real quote. The defense is that an injected instruction can change what is proposed but not what is trusted: eligibility and later scoring read only verified facts, and nothing acts without approval.
- A short or vague posting may produce no requirements. That is shown as a failure with a reason, not an empty success.
- Free-tier model prompts may be used for training. Until a paid no-training tier exists (ADR-0027), only the owner's own pasted jobs should be used.
- Eligibility copy is user-facing English inside `eligibility.py`, so long lines are allowed in that one file.

## Revisit when
Scoring and the evidence agent arrive (1.9), a second source type needs a different acquisition method, postings in other languages need evaluation data (3.6), or the eligibility rules change (bump `RULES_VERSION`).
