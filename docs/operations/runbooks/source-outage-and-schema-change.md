# Runbook: source API outage and source schema change

Jobs come from sources (Greenhouse, Lever, Ashby and others). Each has a circuit breaker, a health state and a fetch log.

## Detection
Health: "<Source> is paused after failures" or "keeps failing", the Sources page shows a failing source and fetch outcomes, or jobs from a source stop appearing.

## Diagnosis
1. Sources, Recent fetches for that source: the HTTP status and the error class of each attempt.
   - 429: you are going too fast for that source. Raise its minimum poll interval.
   - 5xx or timeouts: the source is down. It is not your fault; the breaker pauses it and tries again.
   - 403 or 401: access changed (a key, a block, new terms).
   - 200 with jobs seen = 0, or "schema" error class: the response shape changed (a schema change).
2. Read the source page in `docs/providers/` and the source's own documentation or status page.

## Mitigation
- Outage: wait. The breaker retries with a growing pause. Other sources keep working. Do not hammer it.
- Rate limit: raise the minimum poll interval for the source (Sources, or the `job_sources` row) and let it recover.
- Access or terms: read the terms again. If they now forbid what you do, switch the source off and mark its compliance status (Admin, Sources). People can still bring jobs from it by pasting or importing.
- Schema change: switch the source off, keep the sample response, and fix the adapter (see below).

## Recovery
For a schema change: save a sample of the new response, change the adapter in `pv_worker` (or `pv_domain.source_registry` for the mapping), add a test with that sample, deploy, switch the source on and use Fetch now. Check a few jobs read correctly.

## Prevention
Per-source breakers and health, polite poll intervals, adapters that validate what they read and fail loudly on a shape they do not know, and the terms check dates that expire a source's approval so it is reviewed on a schedule.
