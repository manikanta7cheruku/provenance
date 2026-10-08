# ADR-0015: Postgres RLS as defense in depth

Status: Accepted (Phase 0)

## Context
RLS on every tenant table in addition to repository scoping.

## Problem
A missing WHERE clause must fail closed.

## Options considered
Application checks only; RLS plus application checks.

## Decision
RLS with SET LOCAL app.user_id per transaction, FORCE, non-owner role.

## Why
Two independent layers.

## Consequences
Pooling hazards if session variables are set without LOCAL. Slight overhead.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Fine. |
| 10,000 | Index tuning for policy predicates. |

## Revisit when
Performance profile shows policy cost dominating, with an equivalent safe alternative.
