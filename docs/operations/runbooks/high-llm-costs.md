# Runbook: high model costs

## Detection
Health: "Daily model spend is nearing the ceiling" or "over the ceiling" (needs `LLM_DAILY_SPEND_CEILING_USD`), a rise on Cost and usage, or the provider bill.

## Diagnosis
1. Cost and usage, 7 and 30 days: which model, which operation (purpose) and which day account for it? The page names no one, but it shows the heaviest account's share.
2. Is it more people, more calls per person, or one expensive operation? Compare calls and tokens per call.
3. Failures cost too: a high failed-call count means retries are spending money.
4. Abuse or a stolen key looks like a sudden jump on one operation or at night. Check the audit log and failed sign-ins.

## Mitigation
- Lower the plan limit for the operation that spends most. Plans are data: add a migration that updates the `plans` row (ADR-0051). People are told when they reach a limit.
- Set or lower `LLM_DAILY_SPEND_CEILING_USD` so the alert comes earlier.
- A stolen key: rotate it at the provider now (runbook "secret rotation").
- Pause an expensive feature by setting its plan limit to 0.

## Recovery
Check the numbers again the next day. If the limits were too tight, raise them from measured cost, not from a guess (carryover C-131).

## Prevention
Measure real cost per unit, set the limits from it, keep the ceiling set, record the plan on each model call so cost can be added up by plan (C-143), and review the cost page monthly against the economics model.
