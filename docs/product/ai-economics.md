# AI Economics and Cost Model

Status: Draft. Every number below is a **planning assumption** to be replaced by measured values from the usage ledger. No provider price or free-tier limit is quoted here, because those change and must be read from the provider's current pricing page at the time of use.

## 1. Symbols

| Symbol | Meaning |
|---|---|
| P_in, P_out | Price per input and output token of the chosen model (looked up at build time) |
| P_emb | Price per embedding token |
| T | Tokens |
| N_share | Number of users who analyze the same posting |

## 2. Cost per job analysis

A job analysis for one user has a global part and a per-user part.

```
Global (paid once per unique content hash):
  C_extract = T_extract_in * P_in + T_extract_out * P_out

Per user and job:
  C_gate    = 0                                   (deterministic)
  C_agent   = R_unverified * I_avg * (T_iter_in * P_in + T_iter_out * P_out)
  C_embed   = T_new_evidence * P_emb              (only for newly added evidence)
  C_score   = 0                                   (deterministic)

C_job_user = C_extract / N_share + C_agent + C_embed
```

Where R_unverified is the number of requirements that need the agent after cheap deterministic lookups, and I_avg is mean iterations per requirement.

### Planning assumptions for token usage

| Item | Assumed tokens | Notes |
|---|---|---|
| Job description input | 1,000 to 2,500 | Long postings are truncated with a cap |
| Extraction output | 500 to 1,200 | About 8 to 15 requirements |
| Agent iteration input | 800 to 2,000 | Requirement plus retrieved evidence snippets |
| Agent iteration output | 100 to 300 | Tool choice or verdict with evidence ids |
| Iterations per requirement | 1 to 3 | Hard cap enforced |
| Requirements needing the agent | Fewer than total | Exact skill matches resolve via lexical lookup first |

These are starting hypotheses. The Phase 1 observability baseline records actual values, and this table is replaced with measurements.

## 3. Cost per user

```
C_user_month = sum over analyzed jobs of C_job_user
             + resume parsing (once per upload, small)
             + material generations * C_generation
             + preparation generations * C_prep
             + mock interview turns * C_turn
             + fixed per-user share of email, storage, hosting
```

Generation is explicit and user triggered, so the largest controllable costs are the ones the user chooses to spend, and quotas bound them.

## 4. Global caching and amortization

| Cache | Key | Effect |
|---|---|---|
| Requirement extraction | content hash of normalized public posting text | Paid once, reused by every user |
| Embeddings of job requirements | hash of requirement text | Paid once |
| Candidate evidence embeddings | hash of chunk text per user | Re-embedding skipped when text is unchanged |
| Company research summaries | company id plus source retrieval date, with expiry | Shared across users because they derive from public sources only |
| Source fetch results | source, query, time window | Respect each source's minimum polling interval |

Private postings (user supplied) are cached per user, not globally, to avoid leaking one user's content to another (ADR-0013).

Amortization: C_extract / N_share falls as popularity rises. This is why public ATS ingestion, where many users share postings, is cheaper per user than user-imported private postings.

## 5. Local versus hosted models

| Task | Starting choice | Local model viable? | Decision rule |
|---|---|---|---|
| Embeddings | Local sentence-transformers or hosted embedding API | Yes, small and cheap | Pick by measured retrieval quality on the seed eval set |
| Extraction | Hosted | Maybe later | Move to local only if schema validity and recall match hosted on the eval set |
| Agent verdicts | Hosted | Unlikely early | Quality here affects trust. Do not trade it for cost without evaluation |
| Tailoring and preparation | Hosted | Unlikely early | Same |
| Grounding verifier | Code first, small model assist | Possibly | Code does the final check |

Rule: a cheaper or local model replaces a hosted one only when the evaluation harness shows no regression on the metrics that matter for that task. Model routing is configuration.

## 6. Quota assumptions

Quotas are server-side policies over the usage ledger, defined in terms of billable units from business-model.md. Example shape only, to be set from measurement:

| Operation | Free | Paid |
|---|---|---|
| Discovery runs per month | small number | larger number |
| Job analyses per month | small number | larger number |
| URL analyses per month | small number | larger number |
| Material generations per month | very small | larger |
| Mock interview turns per month | small | larger |

## 7. Free-tier economics

Free users cost money. The model:

```
Free_cost_per_user_month = analyses_free_cap * C_job_user_avg + generations_free_cap * C_generation_avg + fixed_share
Acceptable if  Free_cost_per_user_month * free_users  <=  monthly acquisition budget
```

Inputs are unknown until the first cohort. Until then, free usage during the learning phase runs on provider free tiers with test data only. The free tier must not become a production data path for real resumes (see business-model.md section 4).

## 8. Paid-tier economics

```
Margin_per_user = price - C_user_month_p90 - payment_fees - support_share
```

Use the 90th percentile user cost, not the mean, so heavy users do not make a plan unprofitable. Prices are set only after measurement.

## 9. Worst-case cost controls

Controls are layered. Each is enforced in code.

| Layer | Control |
|---|---|
| Per call | Max input and output tokens |
| Per requirement | Max iterations and tool calls |
| Per run | Max tokens, tool calls, wall time. Exceeding yields "Not verified" for remaining requirements |
| Per user per day | Daily token and operation caps independent of plan |
| Per posting | Description length cap before extraction |
| Global | Daily spend ceiling. On breach, new expensive tasks are queued or rejected with a clear message. Alert fires |
| Provider | Provider-side budget alerts configured where offered |
| Abuse | Rate limits, duplicate task suppression through idempotency keys, one analysis per (user, posting) |
| Retry | Retries cap with backoff. A malformed-output loop cannot spend unbounded tokens |
| Kill switch | Config flag disables generation features without a deploy |

## 10. Measurement requirements (from Phase 1)

Every LLM call records: run_id, purpose, model, prompt version, input and output tokens, estimated cost, latency, content hash. The ledger answers "what did this user cost us" and "what did this posting cost us." Phase 3 builds dashboards on top of data that exists from the first workflow.
