# Checkpoint 1.9: The evidence agent, scoring and the trust screen

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.9-evidence-agent-scoring`. Decisions: [ADR-0032](../adr/0032-evidence-agent-and-on-read-scoring.md), with [ADR-0004](../adr/0004-langgraph-for-the-agentic-subgraph-pending-spike.md) resolved. Runbook: [a job check stopped early](../operations/runbooks/job-analysis-failed.md).

A person opens a job they pasted and presses "Check my evidence". For each requirement the agent looks for proof in their own profile, may search again or ask one short question, and ends with a verdict that code has checked. The page shows a band with reasons, each verdict with the posting's words beside the person's own words, and what would change the result.

## 1. Build

**Database (migration 0007, literal SQL).** `job_analyses` (one per posting), `requirement_verdicts` (with citations that keep a hash of the cited text), `agent_questions`, `verdict_feedback`. Row Level Security enabled and forced on all four. The band is not stored.

**Domain (`pv_domain.analysis`).** Verdict, band and state vocabularies, `accept_verdict` (the rules a verdict must pass), `confidence_for`, `score_analysis` (`scoring-1`), `gap_plan`, `seed_query`, the agent limits.

**Agent (`pv_llm.evidence_agent`).** A bounded loop with two read-only tools. Evidence is named by labels assigned in the run. Limits per requirement and per run.

**Persistence (`pv_persistence.analysis`).** Start or continue, save a verdict, ask and answer, skip, finish or fail, feedback, delete. Answers are stored as `user_answer` evidence chunks.

**Worker (`analyze_job`).** Resumable by construction. Visible failures for a missing key and for a provider that stays down on the last attempt, keeping the verdicts earned.

**API.** `GET/POST /api/v1/jobs/{id}/analysis`, answer, skip, feedback. The band, counts, reasons, gap plan and staleness are computed on read.

**Web.** An "Your evidence" section on the job page: start or continue, progress, headline band and reasons, a question card, requirement rows that open to show the posting's words, the person's words, the reader's note and a feedback pair, the gap plan.

**Tests and evaluation.** Unit tests for the rules and the loop, a seed evaluation set (`tests/unit/test_analysis_eval_seed.py`), integration tests including resuming after a worker dies mid-run, web tests and browser tests with axe.

## 2. UX

- Results appear as they are found. Nothing shows a score until every requirement has a verdict.
- Not verified is explained as "no proof was found", never as a lack of skill.
- The posting's words and the person's words each carry a label and a different rule, never color alone.
- The agent asks at most three short questions and never the same one twice. Skipping is always allowed.
- Hard blockers say so and no score is shown.

## 3. Technical acceptance criteria

1. Migration 0007 applies after 0006 and reverses. All four tables have forced Row Level Security. Other tenants and "no tenant" see nothing, and a forged insert is refused.
2. A verdict is stored only if its citations are labels shown in that run and its quotes are found in that evidence. A made-up quote, a label never shown, a missing citation, a missing evidence kind and an unknown verdict are all rejected.
3. Inferred evidence never makes a requirement Met.
4. At any limit the requirement is Not verified with a reason, never Met.
5. A worker that dies midway resumes and checks only the requirements that have neither a verdict nor a question. A task from an older start or another owner does nothing.
6. The last failed attempt marks the check failed and keeps the verdicts. Starting it again continues.
7. An answer becomes searchable evidence and the next run cites it. A question the person answered is never asked again. Skipping stores Not verified and can finish the check.
8. The band follows the thresholds of `scoring-1`, a conflict caps it at Review, nice-to-haves never change it, a failed gate is Not eligible, and a changed preference changes it at once.
9. Editing a cited entry marks the check as out of date.
10. Feedback is stored with the scoring and prompt versions and answering again replaces the earlier answer.
11. Deleting the job deletes its answers and cancels waiting tasks. Reading the posting again drops the old check.
12. Another person's job is 404 on every route. CSRF, authentication and rate limits are enforced. Audit events hold no text.
13. Ruff, mypy, import-linter, unit and integration tests and the web checks pass.

## 4. UX acceptance criteria

1. An empty answer is explained next to the field and focus moves to it.
2. Progress reads "N of M checked" and updates by itself.
3. A blocked start says why in one sentence.
4. A changed cited entry is called out on the verdict and at the top.

## 5. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the evidence section when not started, working, asking, ready (rows opened), failed and blocked, in light and dark. The state line is a live region. Each verdict opens with the keyboard. Feedback buttons are a labelled group with a pressed state. No horizontal scroll at 375 pixels.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_analysis_domain.py` | acceptance, confidence, bands, gap plan, seed query, state mapping |
| `tests/unit/test_evidence_agent.py` | the loop with a scripted model: verified and rejected verdicts, search again, list entries, questions, limits, bad format, delimiting |
| `tests/unit/test_analysis_eval_seed.py` | the seed evaluation set: 15 verdict cases and 10 band cases |
| `tests/integration/test_analysis.py` | schema and isolation, a full run, band on read, forged citation, staleness, restart, resume after a dying worker, last-attempt failure, questions, feedback, deletion, rate limits |
| `src/features/opportunities/evidence-check.test.tsx` | states, rows, labels, questions, feedback |
| `e2e/analysis.spec.ts` | axe in both themes for six states, the full flows, narrow screen |

## 7. Document

[ADR-0032](../adr/0032-evidence-agent-and-on-read-scoring.md), [ADR-0004](../adr/0004-langgraph-for-the-agentic-subgraph-pending-spike.md), [data-model.md](../architecture/data-model.md), [agent-architecture.md](../architecture/agent-architecture.md), [privacy.md](../compliance/privacy.md), [threat-model.md](../security/threat-model.md), [llm-provider-gemini.md](../operations/llm-provider-gemini.md), the [runbook](../operations/runbooks/job-analysis-failed.md) and index, [product-requirements.md](../product/product-requirements.md), the roadmap status.

## 8. Commit

```
feat(agent): add the evidence resolution agent, scoring and the trust screen
```

## 9. Interview defense

You should be able to explain:
- What makes this an agent and why exactly one: it chooses among tools at run time, judges whether it has enough, and stops, asks or gives up.
- Why code, not the model, decides whether a verdict is accepted, and how labels stop it citing what it did not see.
- Why Not verified is a different statement from "lacks the skill", and why absence of proof never becomes Met.
- Why progress is stored as the results themselves, and how a worker killed midway resumes.
- Why the score is computed on read, why there is no partial score, and why a conflict caps the band.
- What the limits are and what happens at each.
- Why the framework was not used, and what was not measured.

## 10. What was verified and what was not

Verified: all tests above, including resuming after a simulated worker death. A live run on the Docker stack through the real queue, worker, database and API, with a stand-in for the AI service that answers by rule: extraction, a question, the answer cited as evidence, the band with reasons, feedback and deletion.

Not verified: a real model. No key was configured here, so the quality of real verdicts, the real number of model calls per job, and free-tier timing are unmeasured. The seed evaluation set covers the rules, not the model. The LangGraph comparison planned in ADR-0004 was not run (stated in ADR-0032).

## 11. Run it yourself

```
.\scripts\pv.ps1 up
```
Open a job you pasted, press "Check my evidence". Without a key it says the checking service is not set up. With a key in `.env` and `.\scripts\pv.ps1 restart worker`, watch results appear, answer the question if one comes, and use "Was this right?" on a few verdicts.
