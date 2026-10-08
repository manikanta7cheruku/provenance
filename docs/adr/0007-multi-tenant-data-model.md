# ADR-0007: Multi-tenant data model

Status: Accepted (Phase 0)

## Context
Single database, shared schema, owner_user_id on every tenant row.

## Problem
Isolation must hold even if application code forgets a filter.

## Options considered
Database per tenant; schema per tenant; shared schema with RLS.

## Decision
Shared schema, owner_user_id, RLS with FORCE, non-owner app role, repository scoping, mandatory isolation tests.

## Why
Cheap to operate and defense in depth. Teams or organizations can be added later through a membership model.

## Consequences
RLS policies need care with pooling and global tables. Slight query overhead.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine. |
| 100 | Fine. |
| 10,000 | Consider partitioning large tenant tables or sharding by tenant. |

## Revisit when
Regulatory or customer demand for physical isolation.
