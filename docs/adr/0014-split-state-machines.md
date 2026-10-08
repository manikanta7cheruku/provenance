# ADR-0014: Split state machines

Status: Accepted (Phase 0)

## Context
One lifecycle for the posting, another for each user's match.

## Problem
A single machine mixes global and per-user states.

## Options considered
One machine; two machines.

## Decision
Posting lifecycle and match lifecycle, validated in code, every transition logged.

## Why
Each machine has one owner and meaning.

## Consequences
Two diagrams to maintain.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Fine. |
| 10,000 | Fine. |

## Revisit when
States proliferate and need regrouping.
