# ADR-0012: Prompt-injection threat model

Status: Accepted (Phase 0)

## Context
Tier 2 untrusted content with minimal blast radius.

## Problem
Job text and repo content can contain adversarial instructions.

## Options considered
Rely on instructing the model to ignore them; isolation and capability minimization.

## Decision
No tools in extraction, read-only user-scoped agent tools, schema validation, length limits, no side effects from content, injection fixtures in tests.

## Why
Defenses fail eventually. Design so failure does little.

## Consequences
Some capability limits.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Same. |
| 100 | Same. |
| 10,000 | Same plus automated anomaly detection. |

## Revisit when
New tools or write capabilities are proposed for the agent.
