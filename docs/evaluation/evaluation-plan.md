# Evaluation Plan

Status: Decided (Phase 0). Awareness starts in Phase 1. Full harness in checkpoint 3.6.

## 1. Phase 1 evaluation awareness (checkpoints 1.6 to 1.9)

- Every prompt, schema and model has a version string. Results store these versions.
- A seed dataset of about 15 to 20 job postings is created with labeling guidelines, covering easy, ambiguous, buried sponsorship, contradictory location, long posting, remote, entry-level, and at least two prompt-injection attempts.
- Deterministic regression tests run in CI using stub models and recorded fixtures: schema validation, eligibility rules, scoring, dedup, evidence acceptance rules.
- Failures are recorded as data: schema failures, grounding failures (verdict cited missing evidence), unsupported verdicts. They are counted per prompt version.
- A small runner can execute the seed set against a real model on demand and store results with versions.

**State at the end of Phase 1 (checkpoint 1.9).** Built: version strings on every prompt and score; ten synthetic job postings with scripted model answers (`tests/job_fixtures.py`) covering a fresher role, US-only with no sponsorship, an internship, a contract, a lead role, an obeyed prompt injection, invented quotes, smart quotes, Hinglish; deterministic regression tests for extraction checks, eligibility, scoring bands and verdict acceptance (`tests/unit/test_analysis_eval_seed.py` holds 15 verdict cases and 10 band cases); a runner, `scripts/eval_seed.py`, that sends the ten postings to a real model and prints how many requirements and facts survived the checks. Not built: the 15 to 20 postings target (ten exist), written labeling guidelines, a stored results table, grounding failures counted per prompt version in the database, and any measurement of real model quality. The "was this right?" labels from 1.9 onward are the raw material for 3.6.

## 2. Phase 3 full harness (checkpoint 3.6)

About 100 labeled jobs, versioned, with written labeling guidelines created before labeling.

| Area | Metrics |
|---|---|
| Extraction | requirement precision and recall, required vs preferred accuracy, seniority, location, sponsorship detection, schema validity |
| Eligibility | false positives, false negatives (weighted as the costlier error), uncertainty handling |
| Evidence agent | verdict accuracy, evidence grounding rate, unsupported verdict rate, retrieval success, unnecessary iterations |
| Ranking | pairwise preference agreement |
| Generation | factual grounding, contradiction rate, unsupported claims, human preference |
| Preparation | claim grounding, relevance to gaps, resource URL validity |

An LLM judge is never the sole authority on factual correctness. Grounding is checked by code against evidence.

## 3. Running

| Suite | Where | Cost |
|---|---|---|
| Fast deterministic | Every CI run | None |
| LLM evaluation | Manual or scheduled, separate job | Tokens |

Results are stored with git SHA, dataset version, prompt and model versions. Regression thresholds block releases once set from baseline data.

## 4. Dataset governance

Versioned, no real personal data, synthetic or public postings with permission, injection cases labeled as such, changes reviewed.
