# ADR-0018: Development stack conventions

Status: Accepted (checkpoint 1.1)

## Context
Checkpoint 1.1 creates the runnable foundation. Several small but lasting choices had to be made, and some deviate from wording in Phase 0 documents.

## Problem
Pick conventions for the repository layout, Python package naming, database access style, container strategy and the order in which supporting services appear, without adding infrastructure that has no user yet.

## Options considered
1. Compose file location: `infra/compose.yml` (Phase 0 sketch) versus `compose.yaml` at the repository root.
2. Package names: bare names (`domain`, `config`) versus a prefix (`pv_domain`).
3. SQLAlchemy: synchronous engine with FastAPI's threadpool versus an asynchronous engine.
4. Images: a minimal multi-stage production image now versus a development image now and a production image later.
5. Mailpit in 1.1 versus when email flows are built.

## Decision
1. `compose.yaml` at the repository root so `docker compose up` works from the project folder. Dockerfiles stay in `infra/docker/`.
2. Prefix `pv_` on every Python import package (`pv_domain`, `pv_config`, `pv_persistence`, `pv_api`). Generic names like `config` collide with other libraries.
3. Synchronous SQLAlchemy (psycopg 3) in the API. Async is reconsidered if measurements show request threads blocked on I/O, and for the worker if concurrent LLM calls need it.
4. One development image now (editable installs, source bind-mounted). The minimal multi-stage production image is built in checkpoint 3.7 with the production Compose file.
5. Mailpit is added in checkpoint 1.3, where the first email flow exists.

## Why
- A root compose file removes a flag that every command would otherwise need.
- The prefix prevents import ambiguity inside a workspace of several packages.
- Row Level Security uses `SET LOCAL` inside a transaction. Synchronous sessions make that transaction boundary explicit and easy to test. FastAPI runs synchronous routes in a threadpool, so this does not block the event loop.
- A production image has no value before there is something to deploy, and writing it later against real needs avoids guesswork.
- Adding a service nobody uses yet is unused infrastructure.

## Consequences
- Phase 0 documents that mention `infra/compose.yml` are superseded by this ADR.
- Threadpool concurrency is bounded (default 40 threads). Revisit if the API becomes I/O heavy.
- Developers run a development image that differs from production. Parity is restored in 3.7 and tested by the deployment drill.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Threadpool is ample |
| 100 | Fine. Connection pool size is the first limit to watch |
| 10,000 | Replicas of the API. Consider async for hot paths, measured first |

## Revisit when
p95 latency is dominated by waiting on I/O inside request threads, or the worker needs high concurrency for external calls.
