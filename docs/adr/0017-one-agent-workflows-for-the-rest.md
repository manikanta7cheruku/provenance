# ADR-0017: One agent, workflows for the rest

Status: Accepted (Phase 0)

## Context
Exactly one agent: evidence resolution. Other LLM features are single calls or bounded workflows.

## Problem
Labeling everything an agent adds cost and opacity without autonomy.

## Options considered
Many agents; one agent plus workflows.

## Decision
Evidence resolution (with human escalation) is the agent. Tailoring, grounding verification, company research and preparation are workflows where code owns control flow. Mock interview has adaptive routing inside a bounded workflow and is promoted only if evaluation shows it is needed.

## Why
Agentic control flow is justified only where runtime decisions cannot be expressed in code.

## Consequences
Some adaptive behavior is simpler than a true agent.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Same. |
| 100 | Same. |
| 10,000 | Same. |

## Revisit when
Evaluation shows a workflow underperforms an agent for a task.
