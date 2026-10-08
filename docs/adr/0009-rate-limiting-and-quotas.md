# ADR-0009: Rate limiting and quotas

Status: Accepted (Phase 0)

## Context
Policy driven rate limits and usage-ledger quotas, separate from business logic.

## Problem
Abuse and cost control need to exist before public use.

## Options considered
Per-endpoint hardcoded limits; reverse proxy only; policy service with ledger.

## Decision
RateLimitPolicy backed by Postgres counters, QuotaService over UsageLedger. Limits are configuration.

## Why
Request rate and expensive-operation quotas are different problems. Both enforced server side.

## Consequences
Counters in Postgres add write load.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Trivial. |
| 100 | Fine. |
| 10,000 | Move counters to in-memory or Redis if measurements show contention. |

## Revisit when
Rate limit writes appear in the top database load contributors.
