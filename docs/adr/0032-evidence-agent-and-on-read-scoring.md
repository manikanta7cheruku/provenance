# ADR-0032: The evidence agent as a bounded loop in our own code, and scoring computed on read

Status: Accepted (checkpoint 1.9). Resolves the pending part of [ADR-0004](0004-langgraph-for-the-agentic-subgraph-pending-spike.md). Builds on [ADR-0005](0005-human-approval-boundary.md), [ADR-0011](0011-evidence-grounded-matching.md), [ADR-0012](0012-prompt-injection-threat-model.md), [ADR-0026](0026-deterministic-scoring-and-learned-ranker.md) and [ADR-0031](0031-job-paste-extraction-and-eligibility.md).

## Context
Checkpoint 1.9 builds the one real agent in the product: for each requirement of a pasted job it looks for proof in the person's own evidence, may search again with other words, may ask the person a question, and ends with a verdict that code has checked. Around it sit deterministic scoring, bands with reasons, a plan for closing gaps, and a "was this right?" label.

## Problem
What runs the loop, where does its progress live so a crashed worker can resume, and when is the score computed?

## Options considered
| Question | Options | Result |
|---|---|---|
| Runtime | LangGraph with its Postgres checkpointer, a loop in our own code | Our own loop (see "Honest note on the spike") |
| Where progress lives | a separate checkpoint blob, the results themselves | The results themselves. A verdict is stored the moment it is accepted and a question the moment it is asked. Restarting reads what exists and does only what is left |
| First search | the requirement sentence, key words joined with OR | Key words joined with OR. Keyword search needs every word of a plain query in one entry, so a whole sentence found nothing in the first live trial of the tests (`seed_query`) |
| Tools | write-capable, read-only | Two reads of the signed-in person's own evidence: search, and list entries of one kind. The owner id comes from the task, never from model output |
| Naming evidence | database ids, short labels | Labels (E1, E2) assigned by code in this run. The model cannot cite what it was not shown, and cannot cite another person's rows |
| Accepting a verdict | trust the model, check in code | A Met, Partial or Conflicting verdict is accepted only if every citation is a label shown in this run and its quote is found in that evidence. Inferred evidence caps Met at Partial. Otherwise the loop continues, and when limits are spent the requirement is Not verified |
| Confidence | the model's own, from the evidence | From the evidence: Met on direct evidence is High, other supported verdicts Medium, Not verified None |
| Score | stored when the run ends, computed on read | Computed on read from the verdicts and the person's current eligibility, as eligibility is (ADR-0031). A changed preference changes the band at once, and there is never a stale band. There is no partial score |
| Hard gates | blend into the score, short-circuit | Short-circuit. A failed gate is Not eligible with no score, and the check refuses to start |
| Requirements decided by gates | check with evidence, skip | Skipped. Work authorization and location requirements are decided by the eligibility rules |
| Person's answers | one-off, kept as evidence | Kept as evidence (`user_answer` chunks) so they are searchable and traceable. Deleting the job deletes its answers |
| Feedback | free text, a right or wrong label | A right or wrong label per verdict and for the recommendation, stored with the scoring and prompt versions (ADR-0026) |

## Decision
1. **Loop.** `pv_llm.evidence_agent.resolve_requirement`. One initial code-run search, then up to four model steps per requirement. Each step the model chooses search, list entries, ask the person, or give a verdict. Limits: 4 model calls and 3 tool calls per requirement, 90 model calls and 3 questions per run, a ten minute deadline. At a limit the requirement is Not verified with the reason. It never becomes Met.
2. **Durability.** `analyze_job` is idempotent and resumable. `job_analyses.resume_seq` is part of the task key, so a task from an older start does nothing. Transient provider trouble is retried; on the last attempt the check is marked failed, keeping every verdict earned. Starting a failed check continues it; starting a completed one starts over (answers the person gave are kept).
3. **Human in the loop.** The agent asks at most three questions per run and never one the person already answered. The check does not wait on a question: other requirements finish. Answering stores the answer as evidence and queues the agent again. Skipping stores Not verified.
4. **Scoring `scoring-1`.** Coverage of required items, counting Met as 1 and Partial as one half: at least four fifths with no conflict is Strong, three fifths Good, about a third Review, less Not recommended. A conflict caps the band at Review. Nice-to-haves are shown and never change the band. Every band comes with reasons in plain words. Numbers are shown as counts.
5. **Staleness.** Each citation keeps the hash of the evidence text. If the entry was edited or removed, the screen says so and offers to check again.
6. **Gap plan.** For each required item that is not Met, fixed templates by category say what would count as proof and the next step. Nothing is generated.
7. **API.** `GET/POST /api/v1/jobs/{id}/analysis`, `POST .../questions/{qid}/answer`, `.../skip`, `POST .../feedback`. Rate limited, CSRF protected, audited without the text. Another person's job is 404.

## Honest note on the spike
ADR-0004 planned a measured comparison of LangGraph and a hand-rolled loop. That comparison was not run. The decision here rests on design reasoning: this agent has one loop, four actions, and progress that already lives in ordinary tables, so the parts a framework would provide (state, checkpoint, interrupt) are a few dozen lines on top of data we store anyway, and a dependency would add upgrade risk for little saving. The state schema and the tools are ours either way, so the choice can be reversed. Revisit when the graph grows (several agents, branching) or the loop code becomes hard to reason about.

## Consequences
- The model sees the person's evidence text (profile entries and answers) and the requirement. On a free tier that text may be used for training (ADR-0027), so only the owner's own data should go through it until a paid no-training tier exists.
- Only part of a requirement can be shown to be supported: Met is a statement about words in the person's entries, not a guarantee of skill. The screen says what the quote is and where it came from.
- One agent run costs up to about four model calls per requirement. A free tier rate limit sets how long a run takes. The result appears as it is found.
- If two answers are submitted close together, two tasks may run and a requirement could be checked twice. The second save is ignored, so results stay correct and only a model call is wasted.
- Quality of real model verdicts is unmeasured. The seed evaluation set covers rules and bands, not the model. Real measurement waits for labeled cases (3.6).

## Scale analysis
| Users | Posture |
|---|---|
| 10 | One worker is enough. Rate limits of the provider decide the time per job |
| 100 | Same. Per-user limits on starts (20 per hour) keep cost bounded |
| 10,000 | Per-user quota (3.3) and a paid tier. Queue concurrency per user so one person cannot fill the worker |

## Revisit when
Several agents or branching appear, the loop becomes hard to follow, evaluation shows the thresholds in `scoring-1` are wrong, or a learned ranker is proposed under ADR-0026.
