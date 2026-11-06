# Checkpoint 3.6: The evaluation harness

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.6-evaluation`. Decision: [ADR-0054](../adr/0054-evaluation-harness-and-the-ranker-decision.md). Plan: [evaluation-plan.md](../evaluation/evaluation-plan.md). Rules: [labeling-guidelines.md](../evaluation/labeling-guidelines.md). Runbook: [Evaluation](../operations/runbooks/evaluation.md). Builds on the checks from [1.9](checkpoint-1.9.md), [2.4](checkpoint-2.4.md) and [3.2](checkpoint-3.2.md), and the console from [3.5](checkpoint-3.5.md).

## What this checkpoint is for
Say how well our own checks do, notice when a change makes them worse, and measure a real model on the same postings, without a model ever grading a model.

## 1. Build
- **Dataset `jobs-v1`**: 100 synthetic postings with 610 labeled requirements and 646 labeled facts, tagged for injections, buried sponsorship, US-only roles, remote, entry, senior and internship. Rebuilt by a test and saved as a file, so it changes only when its version does.
- **Labeling guidelines**, written before the labels.
- **Six deterministic suites** (extraction grounding, eligibility, evidence verdicts, scoring bands, ranking, claim checking): 19 metrics over 892 cases, each with a limit and a baseline.
- **The LLM suite**: the real model reads the same postings through the product's own extraction, compared with the labels (requirement recall and precision, required against preferred, facts, injections followed). On demand only.
- **A regression gate** in the unit tests, proved by making grounding, eligibility and verdict acceptance worse and checking that it fails. CI prints the table.
- **Stored runs** (`evaluation_runs`, migration 0022): suite, dataset version, git commit, versions of the rules and prompts, model, every metric, and the failed cases. Append-only for the application.
- **Admin Evaluation page** (`/admin/evaluation`): choose a run, compare two, see metrics against limit and baseline, suites, and failed cases by suite. Health shows the latest result and a failing run raises an alert.
- **The learned-ranker decision** (ADR-0054): not adopted, with the numbers that would change it, and a tested function that says why.
- **Command**: `python -m pv_eval run [--store] [--llm] [--update-baseline]`, `dataset`, `write-dataset`.
- Package `pv_eval`, domain module `pv_domain.evaluation`, migration 0022, routes `/admin/evaluation`.

## 2. UX
- Metrics are named in words with their limit ("at least 0.99"), their baseline and a state written out ("Within its limit", "Worse than its baseline", "Outside its limit", "No baseline yet"), never only a color.
- The page says plainly what a pass proves (our checks behave as written on synthetic postings) and what it does not (a real model on real postings).
- The known limit is shown as a failed case with its note, not hidden.

## 3. Technical acceptance criteria
1. The dataset is rebuilt identically, matches its saved file, and every label is true of its text.
2. Every deterministic metric is inside its limit and no worse than its baseline, and a metric with no baseline fails the gate.
3. The gate fails when grounding, eligibility or verdict acceptance is made worse.
4. The LLM suite scores a perfect stand-in model perfectly, a poor one lower, counts an obeyed injection, and scores a model that fails every call as zero.
5. A stored result cannot be changed or removed by the application, and holds no personal data.
6. A failing latest run shows as a warning on Health and raises an alert, and a later pass clears it.
7. The learned ranker is refused with every reason that applies, and accepted only on a measured win over enough labels from enough people.
8. Ruff, mypy, import-linter, unit tests, the integration tests for this checkpoint, and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on a passing run, a failing run with a comparison, a model run and the empty state, in light and dark, and nothing scrolls sideways at 390 pixels. Every state is a word. Selects are labeled. Tables have captions and row headers.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_evaluation.py` | arithmetic, judging, ranker decision, dataset, suites, the gate, report, LLM suite, command (44) |
| `tests/unit/test_observability_rules.py` | the evaluation alert (1 added) |
| `tests/integration/test_evaluation_views.py` | stored runs, admin views, append-only, health (13) |
| `e2e/evaluation.spec.ts` | the page in every state, axe in both themes, a phone (17) |

## 6. Not verified
A real model on the dataset (C-149). Real postings labeled by people (C-148). Generation quality beyond the claim check: contradictions, human preference, preparation relevance and resource links (C-150). The count of feedback labels, which cannot be read by administrators yet (C-151). A scheduled LLM run (C-152). A screen reader pass (C-153). The full 28 minute backend suite was not run for this checkpoint by agreement. It runs after all checkpoints are built.

## 7. What is next
3.7, security hardening, production deployment, backups, legal pages and the remaining runbooks.
