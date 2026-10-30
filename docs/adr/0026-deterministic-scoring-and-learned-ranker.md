# ADR-0026: Deterministic scoring now, learned ranker later

Status: Accepted. Builds on [ADR-0011](0011-evidence-grounded-matching.md) and [ADR-0017](0017-one-agent-workflows-for-the-rest.md).

## Context
The question came up whether classic machine learning (for example gradient boosted trees such as XGBoost) could replace some LLM work. Classic models are good on tabular data and cannot read documents or write text. Training them needs labeled outcomes, and the product has none yet.

## Problem
Where, if anywhere, should a trained model be used, and what must happen before it is allowed to affect what users see?

## Options considered
| Option | Result |
|---|---|
| Learned ranker from day one | No training data exists. Not possible |
| Deterministic, versioned scoring with reasons | Chosen for now. Explainable, testable, matches the evidence-first principle |
| Never use a learned model | Gives up a likely improvement once data exists |

## Decision
1. Scoring and bands are deterministic, versioned code (FR-SCO-1). Every number has a reason.
2. From checkpoint 1.9, each verdict and each recommendation offers a "was this right?" feedback action. Answers are stored as labels with the scoring version and model versions. Labels contain no resume text beyond what the verdict already references.
3. At checkpoint 3.6 the evaluation harness compares a learned ranker trained on those labels against the deterministic baseline on held-out data.
4. A learned ranker may only reorder or flag within the explainable output. It never overrides hard eligibility gates and never changes a verdict's evidence. Adoption needs a measured win and a new ADR.
5. Non-LLM models may also be considered for narrow extraction steps (for example entity extraction) to reduce cost, judged by the same harness. No claim about savings is made before measurement.

## Why
Explainability and trust are the product. A learned model is welcome only where it is measured to help and cannot hide a reason.

## Consequences
- The feedback action is a small addition to the 1.9 UI and a new table.
- Label quality and volume determine whether step 3 is worthwhile. The answer may be no.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Too few labels. Deterministic only |
| 100 | Labels accumulate. Review them manually |
| 10,000 | Train and evaluate. Adopt only on a measured win |

## Revisit when
There are enough labels to train and evaluate meaningfully, which the evaluation harness will state explicitly.
