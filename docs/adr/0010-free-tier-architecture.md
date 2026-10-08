# ADR-0010: Free-tier architecture

Status: Accepted (Phase 0)

## Context
Plans map to entitlements, quota policies and the ledger. No billing integration yet.

## Problem
A free tier must be possible without rewriting features, and numbers must come from data.

## Options considered
Hardcode plan checks; external billing first; entitlement abstraction.

## Decision
Plan to Entitlements to QuotaPolicy to UsageLedger to RateLimiter. Billing is a separate later concern.

## Why
No code path checks plan names. Plans change by data.

## Consequences
Abstraction cost up front.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | One plan. |
| 100 | A few plans. |
| 10,000 | Many plans, add-ons, enterprise. |

## Revisit when
Billing introduces requirements the model cannot express.
