# Checkpoint 3.5: Observability, the Run Inspector and the Admin Console

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.5-observability`. Decision: [ADR-0053](../adr/0053-observability-and-the-admin-console.md). Requirements: [admin-operations-requirements.md](../operations/admin-operations-requirements.md). Runbook: [Alerts](../operations/runbooks/alerts.md). Builds on the queue and run records ([1.4](checkpoint-1.4.md)), the job sources ([2.5](checkpoint-2.5.md)) and the plans work ([3.3](checkpoint-3.3.md)).

## What this checkpoint is for
Answer an operator's questions (is it healthy, why are jobs not appearing, is work stuck, what does it cost, is anyone abusing it) without ever being able to see what anyone wrote, and let a person read why their run failed.

## 1. Build
- **Health page** (`/admin`): what needs attention, each part and its state, request error rate and speed, work that is retrying or stuck, each switched-on source, security events and rate limits exceeded, and how the alerts are decided.
- **Alerts**: 15 rules over one snapshot, each with what to do first and a runbook. A command, `check-alerts`, prints them and exits 1 when anything is critical.
- **Cost and usage** (`/admin/usage`): calls, failures, tokens and estimated cost by model, operation and day, for 7 or 30 days. Aggregate only.
- **Find a run** (`/admin/runs`): the queue's tasks and the model calls for a run reference, from system tables only.
- **Job sources** (`/admin/sources`): each source's state, last success and failure, failures in a row, open jobs, recent fetches, and Fetch now.
- **Queue** (`/admin/queue`): the earlier system page, kept (workers, dead letters, requeue).
- **Run Inspector** (`/runs/:id`): what the run was about with a link, a failure explained with what to do, totals, plain step labels with counts, and the reference to quote.
- Settings `LLM_DAILY_SPEND_CEILING_USD` (off at 0). No new table and no migration.
- Code: `pv_domain.alerts`, `pv_domain.run_explain`, `pv_api.metrics`, `pv_persistence.observability`, `observability_service`, routes `/admin/health`, `/admin/usage`, `/admin/trace/{id}`.

## 2. UX
- Every line answers one question. No decorative charts. Health, cost and trace are tables and sentences.
- A state is always a word, never only a color. "Not measured" is shown as such and never as healthy.
- Alerts name what is wrong, what to do first and the runbook.
- A failed run says what happened and what to do, and never shows the raw error class.

## 3. Technical acceptance criteria
1. Only an admin can read any console route. Everyone else gets 404.
2. The console reads no tenant table. A test fails if its source names one.
3. Every alert rule fires at its threshold and not below. A missing measurement fires nothing.
4. Every alert has a title, detail, action and runbook.
5. Cost is added up by model, operation and day and never names an account.
6. A run can be traced from its reference using tasks and model calls only.
7. A failed run explains itself, shows totals, plain steps with numbers only, and links to what it was about.
8. Another person cannot open a run.
9. The check command exits 1 for a critical alert and 0 otherwise.
10. Ruff, mypy, import-linter, unit tests, the integration tests for this checkpoint, and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on health (healthy and critical), cost and usage, a traced run, sources (with fetches open), the thresholds when opened, and a failed run, in light and dark, and nothing scrolls sideways at 390 pixels. Status is a word plus a shape. Buttons that act on one source name it.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_observability_rules.py` | alert rules, request statistics, words for a run (32) |
| `tests/integration/test_observability.py` | the console, usage, trace, the person's run and the command (22) |
| `e2e/console.spec.ts` | every page, axe in both themes, a phone (27) |

## 6. Not verified
Thresholds against real traffic (C-140). Alert delivery to a channel (C-141). Request statistics across processes and tracing (C-142). Cost by plan (C-143). The evaluation summary (3.6, C-144). Break-glass access (not built, C-145). A screen reader pass (C-146). Database, disk, connection and backup alerts, and SSRF rejection counts (C-147). The full 28 minute backend suite was not run for this checkpoint by agreement. It runs after all checkpoints are built.

## 7. What is next
3.6, the evaluation harness.
