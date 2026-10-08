# Deterministic vs LLM vs Agentic Register

Status: Decided (Phase 0). Every component is classified once. Changing a class requires an ADR.

## 1. Classes

| Class | Definition | Control flow decided by |
|---|---|---|
| D | Deterministic code or SQL | Code |
| L | Single LLM-assisted call, schema-validated, no tools | Code (one call, bounded retries) |
| W | Bounded workflow: LLM generates, code verifies, code decides whether to loop | Code |
| A | Agentic: the model chooses tools and next steps at runtime within hard budgets | Model, bounded by code |

## 2. Register

| Component | Class | Notes |
|---|---|---|
| Search intent parsing (natural language to structured intent) | L | Output validated against a schema. Filtering itself is SQL |
| Source resolver | D | Registry lookup |
| Discovery, fetching, pagination | D | |
| Normalization, URL canonicalization, salary and date parsing | D | |
| Deduplication | D | Fuzzy matching is a scored function, not an LLM |
| Resume parsing | L | Structured output into profile schema. User corrects the result |
| Job requirement extraction | L | Cached globally by content hash |
| Eligibility engine | D | Four states |
| Evidence resolution | **A** | The agent. Tools are read only and user scoped |
| Ambiguity and human escalation | **A** (part of evidence resolution) | Agent raises a question. Code checkpoints and resumes |
| Scoring and recommendation | D | Versioned config |
| State transitions, quotas, entitlements, rate limits, authorization | D | |
| Tailoring generation | W | Generate, verify claims, regenerate or remove flagged claims, bounded loops |
| Grounding verifier | W | Code checks that cited evidence exists and contains the span. LLM only assists on semantic support. Code has the final say |
| Career preparation: categorization, prioritization, requirement mapping, difficulty caps, progress | D | |
| Career preparation: question generation, answer guidance, concept explanation | L or W | Single calls with evidence as input, then verification of candidate claims |
| Career preparation: mock interview | W, with adaptive routing | Next question depends on the answer. Routing bounded by code and rubric. Promoted to A only if evaluation shows fixed routing is insufficient |
| Company research | W | Fetch from allowed sources by code, summarize with citations |
| Exports | D | Generated from structured data, never from screenshots |
| Admin metrics | D | |

## 3. Agent count

The product defines **one agent**: evidence resolution (including its escalation behavior). Tailoring and preparation are workflows (W) that reuse the same grounding services. Adaptive routing in the mock interview is a workflow with a decision step, not a second autonomous agent. This keeps the agent count at one while honoring the amendment that adaptive preparation may use dynamic routing where it is justified.

Test for adding any agent: it must make runtime control-flow decisions that code cannot express, within budgets, with termination conditions, and evaluation must show it beats a fixed workflow.

## 4. Things that must never be LLM calls

sorting, filtering, pagination, arithmetic, URL normalization, deduplication, state transitions, authorization, rate limiting, quota checks, progress calculation.

## 5. Per-component requirements for L, W and A components

Versioned prompt, versioned schema, model identifier stored with the result, token accounting, failure handling, evaluation fixture, grounding strategy, regression test, cost measurement. For A additionally: explicit state, tool definitions, permission boundaries, termination condition, iteration budget, checkpointing, resume behavior, failure recovery, traceability, human escalation path.
