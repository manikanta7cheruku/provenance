# ADR-0054: The evaluation harness, and the learned-ranker decision

Status: Accepted (checkpoint 3.6). Settles the question left open by [ADR-0026](0026-deterministic-scoring-and-learned-ranker.md).

## Context
Every earlier checkpoint added checks that decide what a person sees: grounding of extracted requirements, eligibility rules, evidence verdict acceptance, scoring bands and the claim check on generated text. Each has unit tests. What was missing is one place that says how well they do, whether a change made any of them worse, and what a real model adds. The risks are a change that quietly lowers quality, a metric that looks good because nothing was measured, an evaluation set so small or so easy that every number is perfect, a model judging a model, and adopting a learned ranker because it sounds modern.

## Decision

**A labeled dataset, versioned and rebuilt by a test.** `jobs-v1` is 100 synthetic postings (ten roles, ten variants) with their labeled requirements, facts and injection sentences, built from blocks so each label is true of its text. It is saved as a file, and a test rebuilds it and fails if the two differ, so it changes only when its version changes. Labeling guidelines were written first (`docs/evaluation/labeling-guidelines.md`).

**Two suites with different jobs.**
- *Deterministic*: runs our own checks over the labels and over hand-written case tables (eligibility, verdicts, bands, ranking, claim checking), with scripted model answers that contain controlled mistakes (an invented quote, a value outside the vocabulary, an obeyed instruction). Free, no model, every build. It is a regression gate.
- *LLM*: the real model reads the same postings through the product's own extraction and grounding, and is compared with the labels (requirement recall and precision, required against preferred, facts, injections followed). Costs tokens, so it is manual or scheduled, never CI. Its limits are starting points and fail nothing until the first real run sets them (C-149).

**Code decides every number.** No model grades a model, and no model is the authority on whether a fact is true: the grounding check and the labels are.

**Metrics have a direction, a limit and a baseline.** A metric is a regression when it crosses its limit or is worse than its saved baseline. The deterministic suite has a tolerance of zero, because it has no noise: any change is a change someone reviews and accepts on purpose with `--update-baseline`. A metric with no baseline is reported as new and fails the gate, so a new metric cannot slip in unjudged.

**Failures are data, and the known limit is shown.** Every failed case is stored with expected and got. A quoted injected sentence survives grounding (it is real text in the posting); that is reported on every run, shown as a failure with a note, and bounded by a ceiling of 1.0 so it can only improve. The ranking labels are a careful reader's judgment, not a formula, so the scorer and the reader disagree on a few pairs; those are listed too.

**Runs are stored.** `evaluation_runs` (migration 0022) is a system table: the dataset is synthetic so a run holds no personal data. It records the suite, dataset version, git commit, the versions of the scoring, eligibility rules, extraction prompt and preparation rules, the model, every metric against its limit and baseline, and the failed cases. The application can add and read rows and cannot change or remove them. The admin Evaluation page selects a run, compares two, and lists failures by suite. Health shows the latest result, and a failing latest run raises an alert.

**The gate.** `tests/unit/test_evaluation.py` fails the build when any deterministic metric is outside its limit or worse than the baseline, and also proves the gate works by making grounding, eligibility and verdict acceptance worse and checking it fails. CI prints the table.

**The learned ranker: not adopted.** The harness measures pairwise agreement with a careful reader for any scorer given as a function. The shipped scorer agrees on 98.7 percent of pairs and a naive met-count ranker on 74.6, so the harness can tell a good ranker from a poor one. A learned ranker may reorder results only if it beats the rules by at least 5 points of agreement on held-out labels, from at least 1,000 labels given by at least 30 people. There are far fewer labels today, and there is no candidate, so the answer is no (`ranker_decision`, tested). It would still never override an eligibility gate or a verdict's evidence (ADR-0026). The label count cannot be shown to administrators yet, because labels live in a tenant table; recording an aggregate counter is a carryover (C-151).

## Alternatives considered
- **An LLM as judge of correctness.** Rejected (evaluation plan): it cannot be the authority on facts. Grounding is checked by code against the evidence.
- **Hand-written real postings now.** Deferred: it needs permission, removal of personal data and a second labeler (C-148). Synthetic postings give a gate today and an honest statement of what they prove.
- **Thresholds from today's numbers only.** Rejected for the LLM suite: a limit invented before data is a guess presented as a standard.
- **Store passing cases too.** Rejected: only failures are worth opening, and counts are kept.
- **A learned ranker now.** Rejected: no labels, no candidate, and the explainable score is the product.

## Consequences
- A change that lowers any deterministic metric fails the build until someone decides to accept it.
- The numbers describe how our checks behave on synthetic postings. They say nothing yet about a real model on real postings.
- Changing the dataset is deliberate: a new version, a regenerated file and a new baseline in one review.
- A suite name, trigger or dataset version stored with a run lets two runs be compared fairly.

## Evidence
Unit tests (44): the arithmetic (rates, precision and recall, weighted error, pairwise agreement with ties), judging every case (ok, new, regressed, below limit, either direction, tolerance), the ranker decision with every reason, the dataset (rebuilt identically, equal to the saved file, 100 postings with every tag, every label true of its text, unique cases, no personal data), the suites (all run, deterministic, the known limit reported, a naive ranker clearly worse, a reversed ranker losing), the gate (passes now, baseline names exactly the metrics, fails when grounding, eligibility or verdict acceptance is made worse), the report, the LLM suite with stand-in models (perfect, missing things, following an injection, a failing provider scoring zero), and the command's exit codes. A bug the tests found: a model that failed every call scored a perfect recall, because expected cases were counted only when the model answered. Integration tests (13): admin only, a run stored and read back whole, newest first with the latest per suite, regressions listed by name, two runs compared metric by metric, unknown runs not found, a stored result cannot be changed or removed, no Row Level Security on a system table, bad suite and trigger refused, health and the alert, and the command storing its report. Browser tests (17) with axe in light and dark and a phone.
