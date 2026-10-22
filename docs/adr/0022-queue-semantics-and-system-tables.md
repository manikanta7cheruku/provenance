# ADR-0022: Queue semantics, payload erasure and system tables

Status: Accepted (checkpoint 1.4). Refines [ADR-0002](0002-postgresql-task-queue.md) and applies the pattern of [ADR-0021](0021-tenant-isolation-implementation.md).

## Context
Email, resume parsing and job analysis must outlive an HTTP request and survive crashes. ADR-0002 chose a PostgreSQL queue. Checkpoint 1.4 builds it and has to settle the details that decide whether it is correct: when a task counts as delivered, what happens when a worker dies, what a task may store, and how the queue fits the tenant isolation model.

## Problem
1. A worker can crash at any point, including after doing the work and before saying so.
2. Two workers must never run the same task at the same moment.
3. A failing task must not retry forever or hammer a provider.
4. Email tasks carry a one-time link token. Tokens must not live in the database longer than needed, and must never be returned by an API or written to logs.
5. The worker serves every tenant, but tenant tables are protected by Row Level Security with no bypass.

## Options considered
| Option | Result |
|---|---|
| Redis or RabbitMQ plus a worker library | Extra system, and enqueue cannot share a transaction with the data change. Rejected (ADR-0002). |
| Run work inside the API after the response (BackgroundTasks, used in 1.3) | Lost on restart, no retry, no visibility. Replaced. |
| PostgreSQL queue, exactly-once claim by a lock only | A crashed worker holds the lock forever or releases it silently. Rejected. |
| PostgreSQL queue with leases, attempts and idempotent handlers | Chosen. |
| Put `tasks` under RLS and give the worker a bypass role | Reintroduces a bypass that ADR-0015 forbids. Rejected. |

## Decision
1. **At-least-once delivery.** A task may run more than once. Every handler must be idempotent.
2. **Claim** with a single `UPDATE ... FROM (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)`. A claim sets `state=running`, increments `attempts`, and sets `locked_by` and `locked_until` (the lease).
3. **Visibility timeout.** A `running` task whose lease has expired is claimable again. The next claim increments `attempts`. A claim that makes `attempts > max_attempts` dead-letters the task instead of running it (poison task protection).
4. **Finishing is guarded.** `complete` and `fail` only succeed while `locked_by` still matches. A worker that lost its lease cannot overwrite a newer attempt.
5. **Retries** use exponential backoff with equal jitter (base 5 s, cap 300 s), computed by pure code in `pv_domain.retry`. A failure is retryable or not (`TaskFailure(retryable=...)`). Non-retryable failures dead-letter immediately.
6. **Idempotent enqueue.** `idempotency_key` is UNIQUE and enqueue uses `ON CONFLICT DO NOTHING`. Enqueue runs inside the caller's transaction, so a task and the row that needs it commit together or not at all.
7. **Payload has two parts.** `args` holds non-sensitive references. `secret` holds personal data and one-time tokens. On success the whole payload is erased. On dead-letter only `secret` is erased. No API returns a payload (a unit test scans the OpenAPI schema for `payload` and `secret`).
8. **Errors are stored redacted and truncated** to 300 characters (database CHECK constraint as well as code). Emails and token-like strings are replaced before storage.
9. **A worker only claims task types it has a handler for.** This keeps rolling deployments safe and makes tests independent.
10. **Graceful shutdown.** SIGTERM finishes the task in hand, stops claiming, removes the heartbeat row. SIGKILL is covered by the lease.
11. **Non-requeueable types.** `send_email` carries a one-time link that is erased on dead-letter, so it cannot be requeued. The admin screen says so and the user requests a new link.
12. **System tables are outside RLS.** `tasks`, `worker_heartbeats`, `llm_calls` and `user_stats` have no Row Level Security. They hold metadata only: there is no column for prompt text, response text, resume text or job text, and a test asserts that for `llm_calls`. `workflow_runs` and `workflow_steps` are tenant data and have RLS enabled and forced. Handlers touch tenant data only through `tenant_session(owner_user_id)`. `llm_calls` is append-only for the application role (UPDATE and DELETE revoked). Where a system table is shown to a user (a run's model calls) the code filters by owner explicitly, and a test proves it.

## Why
- Leases turn "worker died" from a deadlock into a timeout. Attempts bound the damage of a task that kills workers.
- Idempotent handlers make at-least-once safe, which is the only delivery guarantee a database queue can give honestly. Exactly-once effects come from idempotency, not from the queue.
- Transactional enqueue removes the dual-write problem (row saved, task lost).
- Splitting `secret` from `args` lets operators requeue reference-only tasks after an incident while guaranteeing a one-time token never outlives its usefulness.
- Keeping `tasks` outside RLS is the smallest exception that lets one worker serve all tenants, and it stays safe because the table holds no tenant content.

## Consequences
- Polling adds database load (one indexed query per second per worker when idle). Partial indexes keep it cheap.
- A duplicate email is possible if a worker dies after SMTP accepted the message and before completion. Acceptable: a newer token invalidates older links.
- Tasks of a new type wait until a worker that knows the type is deployed. The admin overview shows the oldest waiting task so this is visible.
- Task timing is bounded below by the poll interval (default 1 s).

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Trivial. One worker. |
| 100 | One worker is enough. Add workers with `--scale worker=N`. |
| 10,000 | Measure claim latency and polling load. Move to `LISTEN/NOTIFY` for wake-ups before considering a broker. |

## Revisit when
Queue lag persists after adding workers, polling is a top database cost, or a task type needs ordering or priority guarantees the table cannot give simply.
