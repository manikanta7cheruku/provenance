# Checkpoint 3.3: Plans, entitlements and quotas

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.3-plans-and-quotas`. Decision: [ADR-0051](../adr/0051-plans-entitlements-and-quotas.md). Runbook: [Plans and quotas](../operations/runbooks/plans-and-quotas.md). Builds on the services metered here ([1.9](checkpoint-1.9.md), [2.4](checkpoint-2.4.md), [2.10](checkpoint-2.10.md), [3.2](checkpoint-3.2.md)).

## What this checkpoint is for
Anything that costs money to run needs a fair, visible limit that works before any payment exists. This adds plans as data, a usage ledger, quotas that refuse in plain words, a usage screen, and a payment interface that is switched off.

## 1. Build
- **Plans** Free, Starter, Pro as rows, with limits for four billable units, resumes kept, and PDFs kept per resume. A person on no plan gets the default.
- **Metering** on discovery by sentence, job evidence check, job read from an address, and every piece of generated material (tailoring, drafts, preparation, messages). Idempotent by key.
- **Refusals** as HTTP 429 `QUOTA_EXCEEDED` with what was used, what is allowed and when it restarts.
- **Caps** on resumes and kept PDFs come from the plan.
- **Usage screen** in Settings: meters in words and bars, the reset date, a plan comparison table, recent counted events, and a notice that changing plan is not available.
- **Payments** as a Protocol with `DisabledPayments` only.
- **Operator commands** `set-plan` and `show-plan`.
- Data: migration 0020 (`plans`, `user_plans`, `usage_ledger`), `GET /api/v1/plan`, `POST /api/v1/plan/upgrade` (always 409).

## 2. UX
- A refusal says what was used, what the plan allows, when it restarts, and that nothing was changed.
- Meters say "Nearly at the limit" and "The limit is reached" in words, not only in color.
- Reading, editing and exporting are never counted, and the screen says so.
- The plan section promises nothing it cannot do: no buy button, "Nothing is charged".

## 3. Technical acceptance criteria
1. Plans are data. No code branches on a plan name.
2. Check and charge are atomic per person. Two requests cannot take the last unit.
3. The same event key in the same month is one unit.
4. A bad or missing plan row is only ever stricter. Explicit null is unlimited.
5. The application role cannot change a plan. Row Level Security is enabled and forced on `user_plans` and `usage_ledger`.
6. A refused request changes nothing and returns `QUOTA_EXCEEDED` with a `details` object.
7. A new month starts at zero, judged in UTC.
8. Resume and exported PDF caps come from the plan.
9. Payments cannot start. Upgrade returns 409 and says nothing is charged.
10. Ruff, mypy, import-linter, unit tests, the integration tests for the metered services, and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation in the plan section with meters in every state (ok, nearly, reached) and the recent list open, in light and dark, and nothing scrolls sideways at 390 pixels. Every meter has an accessible name with its numbers. The comparison is a real table with a caption and row headers.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_entitlement_rules.py` | the rules (24) |
| `tests/integration/test_plans_and_quotas.py` | the database and API (15) |
| `e2e/plan.spec.ts` | the plan section, axe in both themes, a phone (11) |

## 6. Not verified
The seed limits against real cost (C-131). A real payment provider (C-132). A failed generation is counted and not refunded. Deep evidence search is not metered separately. A screen reader pass of the plan section (C-133). The full 28 minute backend suite was not run for this checkpoint by agreement. It runs after all checkpoints are built.

## 7. What is next
3.4, server-side exports (CSV, XLSX, DOCX).
