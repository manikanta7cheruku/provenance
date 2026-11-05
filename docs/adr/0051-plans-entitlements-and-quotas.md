# ADR-0051: Plans, entitlements and quotas

Status: Accepted (checkpoint 3.3).

## Context
Everything that costs money to run (a model call, a fetch, a generated document) needs a limit that is fair, explainable and cheap to change. Payment is not chosen yet (ADR-0027), so the limits must work without it, and a person must always be able to see what they have used and why something was refused. The risks are a limit that is wrong in the person's disfavor, a check and a charge that race and let two requests through, a retry that is charged twice, a plan name hard coded into logic, and a refusal that reads like a failure.

## Decision

**Plans are data.** A `plans` row holds an id, a label and a `limits` object (units, resumes, exports per resume). Code reads a limit, never a plan name, so there is no `plan == "PRO"` anywhere. Three rows are seeded (Free, Starter, Pro). The application role cannot insert, update or delete a plan: changing a plan is a migration or an operator action, never a request. Every person has at most one `user_plans` row. With none they get `DEFAULT_PLAN` (free).

**Four billable units**, each a thing that costs money: `discovery_run`, `job_analysis`, `url_analysis`, `material_generation`. Reading a result, editing, exporting what exists, and checking the same job again in the same month are never counted. The period is the calendar month in UTC, with a stated reset date.

**One chain.** Plan, then entitlements (`pv_domain.entitlements`, pure rules), then Quota (the decision), then the usage ledger (what was counted), then the rate limiter (unchanged, a different job: bursts, not months). The ledger has a unique `event_key` per person and month. The same key in the same month is one unit, so a retry, a double click or a worker restart never charges twice.

**Check and charge are one step.** `charge()` takes a per-person `pg_advisory_xact_lock`, counts, decides and inserts in one transaction. Two requests at the same moment cannot both take the last unit.

**Bad data is only ever stricter.** A missing unit reads as 0. A value that is not a non-negative integer reads as 0. An explicit `null` is "no limit", on purpose. A switched-off or missing plan falls back to the default plan, and if that is missing too, to an all-zero plan. A wrong row can lock a person out of a feature, never grant unlimited use.

**A refusal is structured.** HTTP 429, failure class `QUOTA_EXCEEDED`, a sentence that says what was used, what the plan allows and when it restarts, and a `details` object (unit, used, limit, plan, resets_at) the screen can read. Nothing was changed by the refused request.

**Payments are a Protocol with one implementation that says no.** `PaymentProvider` has `DisabledPayments`. Changing plan returns 409 `PAYMENTS_NOT_AVAILABLE` with "Nothing is charged and nothing is collected". The screen shows the plans in a table and no buy button. Choosing a provider is a carryover.

**Plan limits also cap resumes and kept PDFs.** The Studio reads both caps from the plan.

**Usage is visible.** Settings shows each meter in words and a bar ("17 of 20 used. Nearly at the limit"), the reset date, a comparison of the plans, and the recent counted events. Meters never rely on color alone.

## Alternatives considered
- **Hard code limits in settings.** Rejected: a plan change would need a deploy and plans could not differ per person.
- **Count rows in existing tables.** Rejected: deleting a job would refund usage, and units would be implicit.
- **A counter column.** Rejected: no idempotency and no record of what was counted.
- **Refund a failed generation.** Deferred. Today a failed generation is counted once and a retry of the same request is free through its key. Whether to refund is a product decision after real cost data (carryover).
- **Meter deep evidence search separately.** Deferred: the call is already part of a counted check.
- **Pick a payment provider now.** Rejected (ADR-0027).

## Consequences
- A limit is a number in a row. Raising it is a data change.
- A generation that fails is counted. The runbook says so.
- The seed limits are starting points chosen before cost was measured, and the screen says so (carryover C-131).
- The shortlist email stays enabled on the free plan for now.

## Evidence
Unit tests (24): the month and its reset including leap years and a late evening in another zone, the decision at the edge, no limit, zero, an amount above one, the meter states, seed plans grow and cover every unit, round trip, bad rows only stricter, the sentences, payments off. Integration tests (15) with the real database: Row Level Security forced on both tenant tables, plans not writable by the app role, refusal at the limit with a structured error, one key charged once, people independent, a new month starts clean, a limit of zero, an unlimited plan, an inactive plan falls back, resume and export caps, the plan route and the upgrade refusal. Browser tests (11) with axe in light and dark and a phone.
