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

## Addendum (checkpoint 1.1 consistency review)

- User-reversible actions have explicit reverse transitions: unsave (saved to recommended), undo dismiss (dismissed to recommended), undo applied (applied to ready_to_apply), retry (analysis_failed to queued). Each is logged with actor and reason.
- UI-facing analysis states such as Processing and Partial result are derived from the match state plus persisted data. They are not additional states. See the architecture overview and the UX specification section 10.
- The canonical state vocabularies (task, match, resume) are listed in [data-model.md](../architecture/data-model.md) section 8.
