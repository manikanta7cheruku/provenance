# Checkpoint 1.4: Durable work, mail on the queue, run observability and admin foundation

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.4-queue-worker-admin`.

## 1. Build

**Database (migration 0003, literal SQL).** `tasks`, `worker_heartbeats`, `workflow_runs`, `workflow_steps` (RLS enabled and forced), `llm_calls` (append-only for the app role, no content columns), `user_stats` (kept by triggers), and `invites.created_by`, `invites.revoked_at`. See [queue-and-observability.md](../architecture/queue-and-observability.md).

**Queue (`pv_persistence.queue`).** Idempotent enqueue in the caller's transaction, claim with `FOR UPDATE SKIP LOCKED`, leases (visibility timeout), attempts, poison-task dead-lettering, guarded `complete` and `fail`, lease extension, requeue, retention purge. Backoff with jitter is pure code in `pv_domain.retry`. Error text is redacted and truncated in `pv_domain.redaction`.

**Worker (`apps/worker`, package `pv_worker`).** Polling loop, graceful SIGTERM, heartbeat thread, handler registry, `TaskFailure(retryable=...)`, JSON logs, database outage backoff, maintenance purge. Handlers: `send_email`, `system.demo`. New compose service `worker` (same image as the API).

**Mail (`pv_mail`).** SMTP and log mailers with failure classification, templates, `delivery_hint`. Registration, verification, reset and the admin actions now enqueue mail in the same transaction as the token. The API says "queued" and tells the truth per configuration (log, local inbox, real SMTP). Mailpit (`axllent/mailpit:v1.30.5`, UI 8025, SMTP 1025) is part of the default stack.

**State vocabulary (`pv_domain.states`).** TaskState, RunState, StepState, UiState and the mappings. The API returns `ui_state`. `npm run check:states` compares the TypeScript union with the backend list.

**Runs.** `GET /api/v1/runs` and `/runs/{id}` (own runs only: RLS plus owner filters). Screens `/runs` and `/runs/:id` with polling while a run is active. Only workflows create runs, so email never appears there.

**Admin foundation (ADR-0023).** Users (list, search, filters, detail), disable and enable (revokes sessions), revoke sessions, promote and demote, resend verification, send password reset, invites (create shown once, optional email binding, revoke), audit viewer, system overview (queue by state, oldest waiting task, workers, dead letters with requeue, AI usage and cost for 24 hours). Guards: no self-disable, last active admin protected. Counters only, never tenant data. Screens under `/admin`.

**AI plumbing (`pv_llm`).** Provider-independent interface, Gemini REST client with throttling and error classification, usage ledger helper, `python -m pv_llm.check`. No feature uses it yet (1.5 and 1.6).

**Operator tooling.** `scripts/pv.ps1`, [operator-commands.md](../operations/operator-commands.md), three runbooks, [llm-provider-gemini.md](../operations/llm-provider-gemini.md).

## 2. UX

- A user who requests a verification or reset email is told what really happens: queued, with a pointer to the local inbox in development, or "written to the worker log" in log mode. The reset message is identical for known and unknown addresses.
- Runs: one plain-language state vocabulary (Queued, Processing, Waiting for you, Retrying, Completed, Failed with retry, Failed, Cancelled), each with a one-sentence explanation. Empty state explains that nothing is wrong yet.
- Admin: confirm dialogs for every destructive action, results announced in a live region, guard failures explained in words ("This is the only active administrator").

## 3. Technical acceptance criteria

1. Migration `0003` applies on top of `0002`. `docker compose up --build` starts postgres, migrate, api, worker, mailpit, web, all healthy.
2. The same idempotency key enqueues once. Enqueue rolls back with the caller's transaction.
3. Two or more workers never claim the same task (tested with 8 racing threads, and 24 tasks across 4 workers).
4. Kill the worker mid-task, restart it: the effect happens exactly once and `attempts` shows 2. A late report from the old worker is refused.
5. Retries back off, then dead-letter at `max_attempts`. A task that keeps killing its worker dead-letters. Non-retryable failures dead-letter at once.
6. Payloads: erased on success, `secret` erased on dead-letter. No API schema contains `payload` or `secret`.
7. `last_error` is at most 300 characters, enforced in code and by a CHECK, and contains no email address or token-like text.
8. Admin endpoints return 404 to regular users and 401 to anonymous callers. Every admin mutation needs CSRF and writes an audit event.
9. No admin response contains tenant content (marker test).
10. `llm_calls` has no content column and the app role cannot update or delete it.
11. The TypeScript state union equals the backend list.
12. Ruff, mypy, import-linter, unit tests, integration tests and web checks pass. CI is green.

## 4. UX acceptance criteria

1. After requesting a password reset the message says the link will be sent and, in development, where to read it.
2. `/runs` shows loading, error with retry, empty, and populated states. A running run refreshes by itself.
3. An admin can find a user, disable them, see them lose their session, enable them again.
4. An admin can create an invite, copy the code once, and revoke an unused invite.
5. An admin can requeue a dead-lettered task of an allowed type, and is told why an email task cannot be requeued.
6. A non-admin who types `/admin` sees the normal "not found" page.

## 5. Accessibility acceptance criteria

1. Tables have captions, `scope="col"` headers and sit in a keyboard-focusable scroll region.
2. Status is a dot plus text, never color alone.
3. Destructive actions use the native `<dialog>`: focus is trapped, Escape closes, focus returns to the trigger, initial focus is on Cancel.
4. Results and errors appear in `role="status"` or `role="alert"` regions. Page titles change per route and focus moves to the page heading.
5. Controls are at least 44px tall and have visible focus. Forms have visible labels.
6. No motion is used.

Not verified: contrast against the real design tokens (the new styles use the page's own text color and two fixed button colors, `#1f3f7a` and `#8f1d16` with white text). Automated axe checks arrive with the design system in 1.5.

## 6. Test

New test functions (parameterized tests expand to more cases):

| File | Test functions |
|---|---|
| `tests/unit/test_retry_and_redaction.py` | 11 |
| `tests/unit/test_states.py` | 8 |
| `tests/unit/test_mail.py` (replaces the 2 old tests) | 14 |
| `tests/unit/test_worker_handlers.py` | 7 |
| `tests/unit/test_settings_worker.py` | 4 |
| `tests/unit/test_llm.py` | 10 |
| `tests/unit/test_api_surface.py` | 2 |
| `tests/integration/test_queue.py` | 15 |
| `tests/integration/test_worker.py` | 9 |
| `tests/integration/test_admin.py` | 21 |
| `tests/integration/test_runs_api.py` | 7 |
| `tests/integration/test_mail_flow.py` | 7 |
| `tests/integration/test_schema_1_4.py` | 8 |

`tests/integration/helpers.py` and `conftest.py` changed: `RecordingMailer` now reads queued mail from the database. **Stop the worker before running integration tests** (`.\scripts\pv.ps1 itest` does it). Frontend: `npm run check:states` (new), `check:boundaries`, `typecheck`, `build`. Not automated yet: browser end-to-end tests and axe (1.5).

## 7. Document

[ADR-0022](../adr/0022-queue-semantics-and-system-tables.md), [ADR-0023](../adr/0023-admin-scope-and-guards.md), ADR index, [queue-and-observability.md](../architecture/queue-and-observability.md), [operator-commands.md](../operations/operator-commands.md), three runbooks and the runbook index, [llm-provider-gemini.md](../operations/llm-provider-gemini.md), provider records for Mailpit and Gemini.

Follow-ups to apply by hand (these files were not part of the supplied context): add a short "Queue and runs" section to `docs/architecture/data-model.md` pointing at the new architecture document, add the admin boundaries sentence from ADR-0023 to `docs/security/security-controls.md`, and replace "Optional compose profile `mail`" mentions in `docs/development-setup.md` if any.

## 8. Commit

```
feat(queue): add postgres task queue, worker, mail package, admin foundation and run views
```
Include the updated `uv.lock` (new workspace members `pv-worker`, `pv-mail`, `pv-llm`; new dependency `httpx` at runtime).

## 9. Interview defense

You should be able to explain:
- Why a database queue gives at-least-once delivery, and why exactly-once effects come from idempotency.
- What `FOR UPDATE SKIP LOCKED` does and why two workers cannot claim one row.
- What a lease (visibility timeout) is, why attempts are counted at claim time, and how poison tasks are stopped.
- Why late workers cannot overwrite a newer attempt (`locked_by` guard).
- Exponential backoff with jitter and the thundering herd problem.
- Why enqueue belongs in the same transaction as the data change (dual-write bug).
- Why `tasks` is outside RLS while `workflow_runs` is inside, and why that is safe.
- Why admins see counters, not content, and how that is enforced rather than promised.
- Why the API says "queued" and why the delivery hint cannot leak which emails exist.
- How the frontend and backend share one state vocabulary and what stops them drifting.

## 10. What I verified and what I could not

**Verified in my sandbox (actually run):**
- Python syntax compilation of every new and changed `.py` file.
- Parsing of `compose.yaml` and `.github/workflows/ci.yml` as YAML.
- `node --check` on the new Node script. `npm run check:states` logic run against the real `states.py` and `states.ts` (passes) and against a deliberately broken copy (fails with the missing state named).
- The repository's boundary rules run against the new frontend files (`Boundaries OK`).
- A syntax-only TypeScript pass over the new frontend files (no syntax errors). This is not a type check: React and router types were not available.

**Not verified (no network, Docker, database or libraries in my sandbox):** ruff, mypy, import-linter, pytest (unit and integration), the TypeScript type check, the Vite build, PostgreSQL behavior of migration 0003 and every SQL statement, Docker Compose, the Mailpit image pull, PowerShell parsing of `pv.ps1`, a live Gemini call, and the running application. **Nothing in this checkpoint is proven until you run it.**

Likeliest first-run problems, most likely first:
1. `uv.lock` out of date. Run `uv sync --all-packages`, commit `uv.lock`. CI uses `--frozen`.
2. Ruff import order and formatting in new files: `uv run ruff check . --fix`, `uv run ruff format .`. A few long lines in tests and SQL text may need manual wrapping (E501 at 100 characters).
3. mypy strictness in `admin_service.py` (SQLAlchemy `ScalarSelect` and `Row` typing), `queue.py` (`CursorResult` cast) and `runner.py`. Fix the annotation, do not silence broadly.
4. A hard-coded migration revision `0002` somewhere (for example `pv_persistence/health.py` or `tests/integration/test_database_foundation.py`): the API would report migrations "behind". Search with `git grep -n "0002"` and update.
5. Existing tests that assert old email wording ("we sent a confirmation link", "we sent a link to reset the password") or call `create_app(..., mailer=...)`. The messages changed on purpose (the email is queued, not sent).
6. SQL details in migration 0003 (plpgsql quoting through Alembic) and in `queue.py` (parameter casts such as `make_interval(secs => :delay)` and `ANY(:types)`). A failing `docker compose logs migrate` shows the exact statement.
7. The Shell navigation edit in the hand-off (one manual change, because `Shell.tsx` was not in the supplied context).
8. Integration tests failing because a live worker consumed queued mail: stop the worker first.
9. Unseen modules importing the deleted `pv_api.mail`. Search with `git grep -n "pv_api.mail"`.

## 11. Run it

See `HANDOFF-checkpoint-1.4.md` (outside the repository) for the full step-by-step with expected output, and [operator-commands.md](../operations/operator-commands.md) for daily use.
