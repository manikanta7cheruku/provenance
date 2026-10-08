# ADR-0005: Human approval boundary

Status: Accepted (Phase 0)

## Context
No application submission capability exists. Generation requires explicit approval.

## Problem
Wrong or unsupported applications harm users. Automation of submission also conflicts with platform terms.

## Options considered
Auto-apply; semi-automatic apply with confirmation; no submission capability.

## Decision
No submission state, no browser automation. Users apply on the employer's site and mark applied.

## Why
The absence of the capability is a safety guarantee, not a policy that can be misconfigured.

## Consequences
Users apply manually.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Same at all scales. |
| 100 | Same. |
| 10,000 | Same. |

## Revisit when
Never, without a new product thesis and legal review.
