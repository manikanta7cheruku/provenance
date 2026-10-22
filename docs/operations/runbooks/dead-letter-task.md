# Runbook: Dead-letter task

A dead-lettered task used up its attempts, failed with a non-retryable error, or killed its worker too many times. It is kept for inspection and never retried automatically.

## Detection
- Admin, System: "Dead letters" lists it with the last error and attempt count.
- `.\scripts\pv.ps1 queue` shows `dead_letter` in the state counts.

## Diagnosis
1. Read the last error. It is redacted and at most 300 characters. Typical values:
   - `SMTP error 550`, `SMTP server refused the recipient`: the address does not exist. Permanent. Nothing to fix.
   - `SMTP connection problem (...)` or `SMTP authentication failed`: mail provider or settings problem. Fix the setting, then see below.
   - `The email details are no longer available`: someone requeued an email task whose one-time link was erased.
   - `Worker lost: attempts exhausted without a result`: the task kept crashing its worker (poison task). Read worker logs around the task time: `.\scripts\pv.ps1 logs worker`.
2. Find related log lines by `task_id` in the worker's JSON logs.
3. Decide: is the cause fixed, or permanent?

## Mitigation
- Fix the cause first (settings, provider outage, code bug).

## Recovery
- **Requeueable types** (for example `system.demo`, and later parsing and analysis tasks that reference ids): Admin, System, "Requeue". The task gets a fresh set of attempts. The action is audited.
- **Email tasks (`send_email`) cannot be requeued.** Their one-time link token was erased on purpose. Ask the user to request a new link (Settings for verification, Forgot password for reset), or use Admin, Users, the user, "Send a new confirmation email" or "Send a password reset email".
- If a task keeps dead-lettering after a fix, stop and open an issue with the task id, type and last error.

## Prevention
- Keep handler error messages free of personal data (they are stored and shown to administrators).
- Classify failures correctly: permanent causes must raise `TaskFailure(retryable=False)` so they do not burn attempts.
- Alert on any new dead letter (checkpoint 3.5).
