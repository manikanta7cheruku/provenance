# ADR-0011: Evidence-grounded matching

Status: Accepted (Phase 0)

## Context
Every verdict and generated claim must cite evidence that code can verify.

## Problem
LLMs produce plausible but unsupported statements.

## Options considered
Trust model output; LLM judge; code-verified citations.

## Decision
Verdicts need existing, user-owned evidence ids with a span present in the chunk. Failure yields Not verified.

## Why
Trust is the product. Verification by code has the final say.

## Consequences
Some true matches are marked Not verified when evidence is thin, which prompts the user to add evidence.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Same. |
| 100 | Same. |
| 10,000 | Same, with faster retrieval. |

## Revisit when
Evaluation shows the rule is too strict and costing useful matches.
