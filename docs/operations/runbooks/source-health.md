# Runbook: Source health, polling and the circuit breaker

A source shows "Paused after failures", jobs are stale or missing, a poll never starts, or a new source needs switching on.

## Detection
- Find jobs: each source shows Healthy, Slow to answer, Paused after failures or Not asked yet, with when it last answered and how many jobs are kept.
- `GET /api/v1/admin/sources`: `health_status`, `failure_streak`, `breaker_open_until`, `jobs_open`, `last_success_at`, `last_failure_at`.
- `GET /api/v1/admin/sources/{key}/log`: the last attempts with outcome, status, counts and error class. No job text is ever logged.
- Admin, Runs and the queue for `poll_source` tasks.

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| Not asked yet | Never polled: not enabled, or the first poll has not run | Check `enabled` and the queue. A source needs a record that is verified and in date |
| Slow to answer | Two or more failures in a row | Read the log for the outcome. Often 5xx or timeouts at the source. No action needed yet |
| Paused after failures | The breaker is open: five or more failures in a row. Nothing is requested until `breaker_open_until` | Wait. One probe is made after the wait. Read the log to see why |
| Log: `rate_limited` | The source said slow down (429). Its Retry-After is obeyed | Raise `min_poll_interval_seconds` for the source if it repeats |
| Log: `bad_response` | The answer was not the expected kind, or every job in it was unusable | The source may have changed shape. Compare with `tests/fixtures/sources`. Update the parser and its test |
| Log: `network_error` | Timeout, connection failure, an oversize answer or a refused redirect | Check the worker network. A refused redirect or an oversize answer says the source changed |
| Log: `not_found` for one board | That board id is wrong or the company left the platform | Fix or remove the company's `ats_board_id`. The source itself is fine |
| Log: `skipped_unusable` | The source is switched off, unverified, expired or has no adapter | Expected. Fix the record if it should be used. No further polls are scheduled |
| Log: `skipped_interval` | The board was asked too recently | Expected |
| Jobs disappeared for everyone | The source stopped being usable (switched off, review expired). Jobs are hidden, not deleted | Renew the review (below) or switch the source back on |
| Polls stopped and nothing is queued | The self-scheduling chain was broken, for example a dead-lettered task | Request a poll (below) or switch the source off and on again |

## Switching a source on (administrator)
1. Read the source's current official terms. Do not rely on repository notes.
2. `PATCH /api/v1/admin/sources/{key}` with `compliance_status` (verified), `terms_checked_at` (today), `verification_owner`, then `enabled` (true). The API and the database refuse if anything is missing.
3. The first poll is queued by itself and each poll queues the next, one slot per poll interval.
4. Look at the log after a few minutes: `ok` with new jobs means it works.

## Requesting a poll now
`POST /api/v1/admin/sources/{key}/poll`. It is queued and audited. Boards asked less than the minimum interval ago are skipped, so this cannot be used to hammer a source.

## Mitigation
Switch a source off with `enabled: false` at once if its terms change or it misbehaves. Its jobs are hidden on the next read and its polls stop.

## Recovery
The breaker clears itself on the first successful probe. To clear it by hand (only if you fixed the cause) set `failure_streak = 0` and `breaker_open_until = NULL` for the source in the database, then request a poll.

## Prevention
Renew each enabled source's review before the window (180 days) ends. Re-check saved fixtures against a real answer when a source changes its API. Do not paste job text into tickets: use the source key, board id and the log counts.
