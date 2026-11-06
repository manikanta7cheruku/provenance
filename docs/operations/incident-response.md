# Incident response

How a security incident is handled, step by step, is the runbook [Security incident](runbooks/security-incident.md). This page holds the rehearsal.

## Roles
There is one operator today. Name a second person who can act if the first cannot be reached, and put both contacts in the password manager (carryover C-161).

## Tabletop: a model key is leaked and abused

The scenario, with the commands and what each step showed on 6 November 2026. This was a walk-through by one person against the production stack on a laptop, not an exercise with a team. It found two mistakes in the runbooks, now fixed.

1. **Detect.** The model bill jumps. Health shows "Daily model spend is nearing the ceiling" (the ceiling must be set: `LLM_DAILY_SPEND_CEILING_USD`). Cost and usage shows one operation and one night.
2. **Contain.** Rotate the key at the provider first (the old one stops working at once), then put the new key in `.env.production` and deploy. The runbook "secret rotation" has the steps.
3. **Assess.** The audit log shows who used what; the model call log has counts and cost, never text. No person's content was exposed by a stolen model key, because the key only lets someone spend money.
4. **Sign everyone out?** The runbook first said to rotate `SECRET_KEY`. The drill showed that does not sign anyone out (sessions are database rows). The command that does is `revoke-all-sessions`, added in this checkpoint. A leaked model key does not need it.
5. **Tell people?** No personal data was exposed, so no notice is needed. If it had been, the runbook says what to tell them and to check what the law requires (carryover C-156).
6. **Learn.** Add the ceiling to the go-live checklist (done in `check-config`: a warning when no ceiling is set), and record the plan on each model call so cost can be traced by plan (C-143).

### Second scenario: an account is taken over
Disable the account (Admin, Users), revoke its sessions, send a password reset, read the audit log for what the account did (exports, deletions). The drill of a `DELETE` request for that account showed the deletion runs in minutes and cannot be undone: if the real owner did not ask, the data is gone except in backups for 30 days. The restore path for one person's data is a restore into a scratch database and a copy of that person's rows by hand; it is not automated (carryover C-162).

## Repeat
Twice a year with at least two people. Write down what was wrong and fix it before the next one.
