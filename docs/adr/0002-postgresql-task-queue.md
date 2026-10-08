# ADR-0002: PostgreSQL task queue

Status: Accepted (Phase 0)

## Context
Durable background work using a tasks table and FOR UPDATE SKIP LOCKED.

## Problem
Long work must outlive HTTP requests and survive crashes.

## Options considered
Redis with a worker library; RabbitMQ; cloud queue; Postgres queue.

## Decision
Postgres queue with attempts, backoff with jitter, visibility timeout, dead letters, idempotency keys.

## Why
No extra system. Enqueue can be in the same transaction as the data change, avoiding dual-write bugs. Delivery is at-least-once, so handlers are idempotent.

## Consequences
Polling load on the database. Lower throughput ceiling than a dedicated broker.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Trivial load. |
| 100 | Fine with tuned polling and indexes. |
| 10,000 | Measure queue latency and DB load. Use LISTEN/NOTIFY or a broker if measurements demand. |

## Revisit when
Queue lag persists after tuning, or database load from polling is a top contributor.
