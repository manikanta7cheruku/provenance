# Checkpoint 3.2: Career preparation

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.2-career-preparation`. Decision: [ADR-0050](../adr/0050-career-preparation.md). Requirements: [career-preparation-requirements.md](../product/career-preparation-requirements.md). Runbook: [Career preparation](../operations/runbooks/career-preparation.md). Builds on the evidence check ([1.9](checkpoint-1.9.md)), tailoring ([2.4](checkpoint-2.4.md)) and application drafts ([2.10](checkpoint-2.10.md)).

## What this checkpoint is for
After a job is checked against a person's evidence, they need to know what to do about it before an interview. This checkpoint adds that, as a workflow on the services that exist, with no new agent.

## 1. Build
- **What to prepare:** how much of the job the profile covers, and every requirement ranked Critical, High, Useful or Optional by versioned rules, with the reason and a difficulty. Tick things off.
- **Practice material** (written by a model, checked by code): interview questions with guidance, questions about the resume and about projects, behavioral prompts, technical concepts, coding topics (software roles), system design (senior software roles). Each item says how much evidence it rests on or that there is not enough, and lists any claim that is not in the evidence.
- **Messages you can send:** an outreach message and a referral request, written from the evidence, checked, editable and copied by the person. Never sent.
- **Mock interview:** one question at a time from the priorities, a gap asked as a gap, each answer scored by a rubric (structure, specifics, relevance, honesty) computed from the answer, claims not in the profile named, a follow-up that points at the next topic.
- **Plan:** give the interview date and get a day by day roadmap, critical first, ending with a review and a mock interview.
- **Company:** what the posting states, and the person's own notes and link (never fetched).
- Data: migration 0019 (`job_preparations`, `prep_outputs`, `prep_progress`, `mock_interviews`), routes under `/api/v1/jobs/{id}/preparation`, a worker task `prepare_job`, a prompt module `pv_llm.prepare`, and the screen at `/opportunities/:id/prepare` with a link from the job page.

## 2. UX
- Hedged words everywhere: "Likely question", "High-priority preparation area", "based on this job description". Never a prediction.
- "Not shown" never means "cannot". The screen says so.
- Insufficient evidence is stated in the product's own sentence, with what to do about it.
- Every failure says what to do. Without a model key only the written material is unavailable and says so.
- Four tabs: What to prepare, Practice material, Mock interview, Plan and company.

## 3. Technical acceptance criteria
1. A required requirement that is not shown is Critical, partly shown is High, a preferred one not met is Useful, anything else Optional. The example in the requirements document ranks AWS first and the partial ones next.
2. Coding appears only for software roles and system design only for senior software roles.
3. Every generated item cites evidence or says there is not enough. Every claim not in the evidence or the job is listed.
4. A requirement that is not shown is never claimed as done.
5. Preparation needs a completed evidence check. Messages need evidence.
6. A task for an older request, or for a deleted output, does nothing.
7. The mock interview feedback is computed from the answer and names claims not in the profile.
8. The plan ends with a review and a mock interview, and no date gives no plan.
9. Nothing is ever sent. No web address, book or person is invented (the prompt forbids them and the company link is never fetched).
10. Row Level Security on all four tables, ownership on every route, audit without text.
11. Ruff, mypy, import-linter, unit tests, the integration tests for this checkpoint, and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on every tab (with material, feedback and a plan) in light and dark, and nothing scrolls sideways at 390 pixels. Questions are native disclosure elements. Every control is labelled. Progress and copy results are announced.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_preparation_rules.py` | the rules (31) |
| `tests/integration/test_career_preparation.py` | the database, API and worker with a stub model (26) |
| `e2e/preparation.spec.ts` | the screen on every tab, axe in both themes, a phone (15) |

## 6. Not verified
Written material on a real model (C-125), the rubric against real answers (C-126), live company research and curated learning resources (C-127), real users practising (C-128), a screen reader pass. The full 28 minute backend suite was not run for this checkpoint by agreement. It runs after all checkpoints are built.

## 7. What is next
3.3, plans, entitlements and quotas.
