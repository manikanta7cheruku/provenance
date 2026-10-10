# Checkpoints 1.2 and 1.3: Authentication, tenancy and security boundaries

Phase 1, Foundation and Core Intelligence. Delivered together because 1.3 builds directly on 1.2.

Order of construction (as specified): authentication, authorization, multi-tenancy, tenant isolation tests, rate limiting, security boundaries.

## 1. Build

### Checkpoint 1.2: identity and tenancy
- Migration `0002`: `users`, `sessions`, `email_tokens`, `invites`, `audit_events`, `rate_limit_buckets`, and the first tenant table `profile_entries` with Row Level Security (enabled, forced, fail closed).
- Argon2id password hashing, opaque server-side sessions (hashed at rest), cookie flags, session rotation and revocation.
- Invite-only registration (`SIGNUP_MODE`), operator CLI: `python -m pv_api.cli create-invite` and `promote-admin`.
- Authorization in dependencies and services: `require_user`, `require_csrf`, `require_verified_writer`, `require_admin`. Roles USER and ADMIN. Admin sees aggregates only.
- Tenant isolation: `tenant_session` sets `app.user_id` transaction-locally. Profile entry CRUD (API only, UI in 1.5) with 404 semantics.
- Authentication UI: sign in, create account, session states, expired-session handling, route guard, account section in Settings.

### Checkpoint 1.3: abuse prevention and security boundaries
- Policy-driven rate limits in PostgreSQL (login by address and by email, registration, reset, verification, password change) with structured 429 responses.
- Security boundaries: Origin check for state-changing requests, CSRF token, request size limit, security headers, `Cache-Control: no-store` on API responses, uniform error shape, append-only audit and security event log.
- Email flows built behind `EMAIL_VERIFICATION_REQUIRED`: verification, password reset, recovery, mail interface with SMTP and development log implementations, optional Mailpit profile.
- UI: forgot password, reset password, verify email, rate-limit feedback, verification banner, accessible form primitives.

## 2. UX

- Calm single-column auth screens outside the shell. No containers. Hierarchy from type, spacing and alignment.
- Forms: labels above fields, hints linked to inputs, validation on submit, errors beside the field and linked with `aria-describedby`, focus moves to the first invalid field.
- Messages say what happened and what to do. Wrong credentials never say which part was wrong.
- Rate limiting is explained with a time ("Try again in about 42 seconds") and the submit button is disabled until then.
- A session that ends (expired or revoked) returns the user to sign in with an explanation and the page they were on is restored afterwards.
- Password reset and verification links work once and explain themselves when they fail.
- Settings shows email status with a way to resend the link, and a change-password form.

## 3. Technical acceptance criteria

1. `uv run alembic ... upgrade head` applies `0001` and `0002` and `docker compose up --build` is healthy.
2. Registration needs a valid, unused invite. Passwords are Argon2id hashes. Sessions, invites and email tokens are stored only as hashes.
3. Login errors for an unknown email and a wrong password are identical in status, code and message.
4. A logged-out or rotated session cookie is refused by the server.
5. Every state-changing request from a signed-in browser needs the CSRF token. A foreign `Origin` is rejected.
6. User A gets 404 on user B's profile entries for read, update and delete, and the list never contains them. Foreign and unknown ids are indistinguishable.
7. Row Level Security filters raw SQL as the application role, blocks writes for another tenant, fails closed with no context, and does not leak between transactions on one connection.
8. An administrator cannot read user data through the API.
9. The audit log cannot be updated or deleted by the application role. Failed logins are recorded without the plain email.
10. Rate limits return 429 with `Retry-After` and a structured body. Counter keys contain no raw email.
11. With `EMAIL_VERIFICATION_REQUIRED=true`, unverified users cannot write and can after verifying.
12. Ruff, mypy, import-linter, unit tests, integration tests and the web checks pass. CI is green.

## 4. UX acceptance criteria

1. A new user can create an account with an invite, land in the app, sign out and sign in again.
2. A wrong password shows one generic message, and the form keeps the email.
3. After repeated failures the user sees how long to wait, and the button is disabled until then.
4. Forgot password always shows the same confirmation. A valid link lets the user choose a new password. Reusing the link explains that it expired.
5. When the session ends the user lands on sign in with "Your session ended" and returns to the same page after signing in.
6. With verification required, an unverified user sees a banner with a resend action and cannot save changes until confirming.
7. Every error says what happened and what to do next. None shows raw technical text.

## 5. Accessibility acceptance criteria

1. Every field has a visible label and, where present, a hint and an error linked by `aria-describedby`. Invalid fields have `aria-invalid`.
2. After a failed submit, focus moves to the first invalid field. Server errors that are not field-specific appear in a live region.
3. Everything is keyboard operable. Focus is always visible. Tab order follows reading order.
4. Inputs use correct `autocomplete` values (`email`, `current-password`, `new-password`) and types so password managers work.
5. Inputs are at least 44px tall. Error and hint text meet contrast (results below). Input borders meet 3:1.
6. The rate limit message and verification banner are announced politely. Status is never color alone.
7. Page title changes per route. Focus moves to the page heading after navigation.

### Contrast results for form colors (WCAG 2.2)

| Theme | Pair | Ratio | Needed | Result |
|---|---|---|---|---|
| light | error text (danger) on page surface | 6.23 | 4.5 | pass |
| light | error text (danger) on raised surface | 6.56 | 4.5 | pass |
| dark | error text (danger) on page surface | 7.28 | 4.5 | pass |
| dark | error text (danger) on raised surface | 6.74 | 4.5 | pass |
| light | secondary text on page surface (hints) | 6.75 | 4.5 | pass |
| dark | secondary text on page surface (hints) | 7.50 | 4.5 | pass |
| light | input border (control) on raised surface | 3.63 | 3.0 | pass |
| dark | input border (control) on raised surface | 4.05 | 3.0 | pass |
| light | invalid input border on raised surface | 6.56 | 3.0 | pass |
| dark | invalid input border on raised surface | 6.74 | 3.0 | pass |

## 6. Test

Test functions (parameterized tests expand to more cases):

| File | Test functions |
|---|---|
| `tests/integration/test_audit_and_security_records.py` | 5 |
| `tests/integration/test_auth_flows.py` | 25 |
| `tests/integration/test_database_foundation.py` | 4 |
| `tests/integration/test_tenant_isolation.py` | 8 |
| `tests/unit/test_api.py` | 11 |
| `tests/unit/test_auth_domain.py` | 14 |
| `tests/unit/test_failures.py` | 2 |
| `tests/unit/test_mail.py` | 2 |
| `tests/unit/test_settings.py` | 15 |

Unit tests need no database. Integration tests need a migrated PostgreSQL and run with `uv run pytest -m integration`.

What the integration suite attacks: invite reuse and email-bound invites, duplicate emails, login uniformity, cookie flags, logout replay, CSRF missing and wrong, foreign Origin, password change rotation, reset single use and expiry, weak password keeps the link alive, verification gating, rate limit 429, admin hidden from users, cross-tenant API access for every operation, client-chosen owner ignored, admin cannot read tenant data, raw SQL isolation (read, write, fail closed, no leakage across transactions), append-only audit, no plain email in audit or rate limit keys.

Not yet automated: browser and end-to-end tests, axe accessibility checks (checkpoint 1.5), load tests.

## 7. Document

[ADR-0020](../adr/0020-sessions-csrf-and-rate-limiting.md), [ADR-0021](../adr/0021-tenant-isolation-implementation.md), updated [security controls](../security/security-controls.md), [data model](../architecture/data-model.md), [UX specification](../product/ux-specification.md), [provider record: Mailpit](../providers/mailpit.md), the ADR index and documentation index.

## 8. Commit

```
feat(auth): add sessions, tenant isolation, rate limiting, security boundaries and auth screens
```

Include the updated `uv.lock` in this commit (a new dependency, argon2-cffi, was added).

## 9. Interview defense

You should be able to explain:
- Why passwords use Argon2id and why the cost is deliberate, and what rehash-on-login does.
- Why session tokens are random and stored hashed, and why that differs from a JWT.
- What each cookie flag does (httpOnly, Secure, SameSite, `__Host-`) and which attack each one stops.
- How CSRF works, why SameSite alone is not enough, and how the derived token and Origin check work together.
- Why unknown email and wrong password must look the same, including timing, and why registration is the accepted exception while invite-only.
- What Row Level Security is, why `FORCE` matters, why `set_config(..., true)` is safe with connection pooling, and what "fail closed" means.
- Why the application role must not be the table owner and why admins have no bypass.
- Why identity tables are outside RLS and how that exception is controlled.
- How a fixed-window rate limit works, its burst weakness, and why keys are hashed.
- Why email is sent after the response and what that costs.
- How you proved isolation: which tests, at which layers.
- What MVCC has to do with transaction-local settings and the queue you build next.

## 10. What I verified and what I could not

Verified in my sandbox: Python syntax compilation of every source and test file, parsing of TOML, YAML and JSON, the frontend boundary script on the merged source tree, documentation links and the consistency checks, and visual rendering of the new screens in a real browser engine using the real CSS (static HTML mirroring the components).

Not verified (no network, no Docker, no libraries in my sandbox): ruff, mypy, pytest, the TypeScript compiler, the Vite build, PostgreSQL behavior, Argon2 and the running application. The code was written to be correct by construction and reviewed line by line, but these must run on your machine.

Most likely first-run problems and where to look:
1. Ruff import ordering and formatting. Fix with `uv run ruff check . --fix` then `uv run ruff format .`.
2. mypy strictness around SQLAlchemy 2 and Starlette types (`src/pv_api/*`, `src/pv_persistence/*`). Fix the annotation, do not silence broadly.
3. The rate limit SQL in `pv_persistence/rate_limit.py` (parameter casts). Symptom: a database error on the first login attempt.
4. `CITEXT` import from `sqlalchemy.dialects.postgresql` (needs SQLAlchemy 2.0.7 or newer, which the lockfile will satisfy).
5. TypeScript errors in the new frontend files. Fix the types.
6. Test assumptions about library behavior (cookie header format, `TestClient(client=...)`, which database exception is raised for a policy violation). If one fails, read the assertion and the actual value before changing code.
7. First `docker compose up` after pulling this checkpoint runs migration `0002`. If it fails, read `docker compose logs migrate`.

## 11. Run it (Windows PowerShell, from the repository folder)

The complete step-by-step with expected output is in `HANDOFF-for-your-AI-assistant.md` (outside the repository). Summary:

```powershell
git checkout main; git pull
git checkout -b phase-1/checkpoint-1.2-1.3-auth-tenancy-security
# copy the package files into the repository (merge, overwrite)
uv sync --all-packages
uv run ruff check . --fix
uv run ruff format .
uv run ruff check .
uv run mypy
uv run lint-imports
uv run pytest
cd apps\web; npm run check:boundaries; npm run typecheck; npm run build; cd ..\..
docker compose up --build
# second terminal
uv run alembic -c packages/persistence/alembic.ini upgrade head
uv run pytest -m integration
```

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| CI fails at `uv sync --frozen` | `uv.lock` not committed after adding argon2-cffi | Run `uv sync --all-packages`, commit `uv.lock` |
| `relation "users" does not exist` | Migration 0002 not applied | `uv run alembic -c packages/persistence/alembic.ini upgrade head` |
| `permission denied for table ...` | Table created before default privileges existed | Should not happen with 0001 applied first. Check `alembic_version` is `0002` |
| Every sign-in attempt returns 429 | All requests share one client address and hit the per-address limit | Wait a minute. Development proxy passes the real address. If it persists, check `--proxy-headers` in compose |
| Sign-in works but the next request says signed out | Cookie not stored | Use http://localhost:5173 exactly (not 127.0.0.1) and check the cookie in browser tools |
| `ORIGIN_REJECTED` in the browser | `PUBLIC_BASE_URL` or `CORS_ORIGINS` does not match the address in the browser | Make them equal to the page origin |
| No email arrives | Development mode logs emails | `docker compose logs api` and look for `DEV MAIL`, or use the `mail` profile |
| Integration tests skip | No `.env` | Create `.env` in the repository root |
