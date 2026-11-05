# Runbook: plans and quotas

## A person says "I hit a limit"
The message says which unit, what was used, what the plan allows and when it restarts (the first of the next month, UTC). Check with the operator command:

```bash
docker compose exec api python -m pv_api.cli show-plan --email person@example.com
```

Nothing was changed by the refused request. Reading, editing and exporting are never counted.

## Give a person a different plan
```bash
docker compose exec api python -m pv_api.cli set-plan --email person@example.com --plan starter
```
It takes effect on their next request. Plans are data: to change a limit, add a migration that updates the `plans` row (the application role cannot).

## A person was charged twice for one thing
Not possible for one request: each charge has an event key and the same key in the same month is one unit. If it looks doubled, the keys differ, which means two separate requests. Look at `usage_ledger` for the person (as the owner role, with the tenant set) and compare `event_key`.

## A failed generation used a unit
By design for now (C-131 covers the decision). A retry of the same request is free. A new "write again" is a new request and a new unit.

## A plan row looks wrong
Missing or invalid values only make limits stricter (0). An explicit `null` means no limit. A switched-off plan falls back to `DEFAULT_PLAN`, then to an all-zero plan. If everyone is suddenly refused, check `SELECT id, active, limits FROM plans`.

## Payments
Disabled. `POST /api/v1/plan/upgrade` always returns 409 `PAYMENTS_NOT_AVAILABLE`. Do not enable anything until a provider is chosen (C-132).

## What to look at
- Tables `user_plans` and `usage_ledger` are tenant data with Row Level Security. `plans` is shared and read only for the application.
- Setting `DEFAULT_PLAN` (default `free`).
