# Runbook: alerts

The Health page (`/admin`) and the command below list what needs attention. Each section here is named like the alert it explains. Thresholds are starting points (see "How these alerts are decided" on the page) and are set in `pv_domain.alerts.Thresholds`.

```bash
docker compose exec api python -m pv_api.cli check-alerts
```
Prints each alert and what to do, and exits 1 when anything is critical, so it can run on a schedule. It cannot measure request timings, which live in the API process.

## The database is not answering
Nothing can be read or saved. Check `docker compose ps` for `postgres`, then its logs and the disk. Start it if it stopped. The API recovers by itself when it answers again.

## The database is behind the code
The running version expects tables or columns that are not there. Run `docker compose run --rm migrate`, then restart the API and worker. Never edit the database by hand to match the code.

## No worker is running
Queued work, including email and every background job, will not run. Start it (`docker compose up -d worker`) and read its log for why it stopped (crash, out of memory, a database it could not reach).

## Work has been waiting a long time
Workers are alive but the oldest task is old. Open Queue to see what each worker handled and Health's "retrying or stuck" table. One slow or stuck task type can hold the others. If it is the model provider being slow, work clears as it answers.

## Some tasks have outlived their lease
A worker took a task and stopped renewing it, usually because it died. The next claim retries the task. If the same task keeps appearing, trace its run and read its error. A task that always outlives its lease is slow, not dead: raise its lease or split the work.

## Tasks gave up
Dead letters need a person. Open Queue, read the reason and, where it says so, requeue. Fix the cause first or it fails again. A one-time email link cannot be requeued: ask the person to request a new one.

## <Source> is paused after failures
The circuit breaker opened after repeated failures. It tries again by itself when the pause ends. Open Sources, read the recent fetches (HTTP status and error class) and check the source's own page for a change or an outage. Do not switch the source off unless its terms changed.

## <Source> keeps failing
The last fetches failed but the breaker has not opened. Same steps. A rate limit (HTTP 429) means the poll interval is too short for that source.

## Many model calls are failing
Check the provider's status page and that the key and model name are right (`GEMINI_API_KEY`, `LLM_MODEL`). Open Cost and usage to see which operation is failing and the error class in a traced run. Retryable errors are tried several times before a run fails.

## Daily model spend is nearing the ceiling / over the ceiling
Open Cost and usage, find the dearest operation and the heaviest day. Lower the plan limits for that operation (a data change, ADR-0051) or pause the feature. Raise `LLM_DAILY_SPEND_CEILING_USD` only on purpose. The ceiling is 0 (off) until it is set.

## The database is running out of connections
Connections in use are above 80 percent of the limit. Look for a stuck worker or API holding sessions open, restart it, and raise the limit or add pooling only if the load is real.

## The API is returning server errors
Read the API log for `unhandled_exception` lines. Each carries a request id that the person saw. Roll back the last release if it started after a deploy. Request statistics are for the process that answered.

## The API is slow
Check the database, the queue and the host. Find one slow route in the request log (`duration_ms`). A slow route that also fails is the previous alert.

## Many failed sign-ins
Open the audit log and look for one address or one account. Rate limits already slow guessing. If it is one account, revoke its sessions and send a password reset from Users.

## Many requests from the wrong origin
Check `ALLOWED_ORIGINS` matches the address people really use. If it does, the audit log's `origin_rejected` events show the paths being tried. A real browser from the right address is never rejected.

## A person quotes a run reference
Open Find a run, paste it, and read the tasks (state, tries, redacted error) and the model calls (model, prompt version, tokens, cost). That is everything an administrator can see. The person sees their own steps on their run page.

## What to look at
- Health: `/admin`. Queue: `/admin/queue`. Sources: `/admin/sources`. Cost and usage: `/admin/usage`. Find a run: `/admin/runs`.
- Setting `LLM_DAILY_SPEND_CEILING_USD`.
- Admin routes read system tables only. They never read a resume, a job or a person's run.
