# Runbook: Stuck task

A task is "stuck" when it stays `queued`, `retry_scheduled` or `running` far longer than expected.

## Detection
- Admin, System: oldest waiting task is large, or the same `running` count never changes.
- `.\scripts\pv.ps1 queue` shows a task with an old `updated_at` and state `running` or `queued`.

## Diagnosis
Decide which of four cases it is:
1. **No worker for this type.** The task type has no registered handler on any running worker (for example a new type before the worker was redeployed). Workers only claim types they know. Fix: deploy or restart the worker.
2. **Not due yet.** State `retry_scheduled` and `run_after` in the future: it is waiting out its backoff. Backoff is at most 5 minutes. This is normal.
3. **Lease still valid.** State `running` and `locked_until` in the future: a worker is working on it (or crashed within the last `WORKER_LEASE_SECONDS`). Wait one lease period.
4. **Running past its lease.** State `running` and `locked_until` in the past: it will be claimed again by the next free worker. If no worker is free, see the Worker failure runbook.

Inspect one task (no payload is shown):
```sql
SELECT id, task_type, state, attempts, max_attempts, run_after, locked_by, locked_until,
       last_error, updated_at
  FROM tasks WHERE id = '<task id>';
```

## Mitigation
- Cases 1 and 4: restart or add workers.
- Never edit `payload` by hand. Never set `state` by hand except as in Recovery.
- A task that repeatedly crashes its worker dead-letters after `max_attempts`, by design.

## Recovery
- A task whose lease is expired and whose worker is gone needs nothing: the next claim recovers it.
- A task you must stop: let it dead-letter, or delete the row only if it has no side effects (`DELETE FROM tasks WHERE id = '<id>' AND state IN ('queued','retry_scheduled')`) and record why in your notes.

## Prevention
- Long handlers must call `ctx.extend_lease()` inside their loop.
- Handlers must be idempotent, so a recovered task never doubles an effect.
