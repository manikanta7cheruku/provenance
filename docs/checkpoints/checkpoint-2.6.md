# Checkpoint 2.6: Adapters, the fetch layer and source health

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.6-adapters-and-fetch-layer`. Decision: [ADR-0038](../adr/0038-adapters-fetch-layer-and-circuit-breaker.md). Records: [source-compliance.md](../compliance/source-compliance.md) and [providers/](../providers/README.md). Runbook: [source health and polling](../operations/runbooks/source-health.md).

This is the first checkpoint that can talk to a job source. It is built so that it asks politely, stops when a source fails, shows only what a source's current record allows, and does nothing at all until the owner has confirmed a source and switched it on.

## 1. Build

**Adapters** (`pv_domain.job_feed`) for Lever, Greenhouse and Ashby: pure parsers into one small record, with HTML reduced to plain text, https-only addresses and limits on every field. Written from the official documentation and checked against one real answer per source (read once on 2026-11-02 with an identifying User-Agent and saved, trimmed, as test fixtures). That reading found three facts the documentation does not stress: Greenhouse sends descriptions as escaped HTML, a full board is 5.8 MB, and Ashby titles can carry a leading space.

**Fetch layer** (`pv_worker.fetcher`). The only network code: https and allowed hosts only, no redirects, size and time limits, an honest User-Agent, no cookies.

**Polite fetching** (`pv_domain.fetching`, the poll task). Minimum interval per board, one request at a time with a gap, Retry-After obeyed, a circuit breaker per source (five failures open it for 15 minutes, doubling to six hours, then one probe), and health words (unknown, healthy, degraded, down) computed from the same counters.

**Poll task** (`poll_source`). Checks the source is usable, asks each due board, keeps the jobs, closes the ones a complete listing no longer holds, writes a log line for every attempt and skip, prunes the log after 30 days, and schedules its own next run while the source stays usable.

**Storage** (migration 0011): `source_jobs` (plain text jobs, unique per source, board and the source's own id), `source_targets` (when each board was last asked), `fetch_log` (outcomes and counts, never job text), and `breaker_open_until` on the source.

**Seen by people.** `GET /search/jobs` lists open jobs filtered in SQL, only while their source is enabled, verified and in date. Find jobs shows those jobs with their source, attribution and a link to the original, and each source's health, last answer and number of jobs kept. For administrators: health and open job counts on every source, the fetch log, and a manual poll that is queued, audited and still bound by the interval.

## 2. UX

- Jobs always say where they came from and link to the original posting.
- A source that stops answering shows "Paused after failures" instead of silently going stale.
- When no source can be searched, the page still says so and offers import. That is still true until a source is enabled.

## 3. Technical acceptance criteria

1. Every parser reads its real saved answer, skips and counts unusable jobs, rejects the wrong kind of answer, and never returns markup or a non-https address.
2. The fetch layer refuses other schemes, hosts, ports and credentials before any request, never follows a redirect, stops oversize answers while reading, keeps no cookies, and turns network failures into one clean error.
3. A board is not asked twice within the interval, from any caller. A manual poll cannot get around it.
4. Five failures open the breaker. Nothing is requested while it is open. One probe follows the wait, success closes it, failure reopens it for longer. A missing board does not count. Another source is never affected.
5. 429 is obeyed with its Retry-After. A bad answer changes nothing and closes nothing.
6. A source that is not enabled, verified and in date is not asked and does not reschedule itself.
7. Jobs vanish from every list the moment their source stops being usable, and are not deleted.
8. Filtering is SQL, wildcards in a search are text, and the list is paged and limited.
9. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on Find jobs with a plan, a company choice and a list of jobs, in light and dark. Health is written as words. Each link to an original posting names the job.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_job_feed.py` | parsers on the real answers and hostile input, the polite fetching rules |
| `tests/unit/test_fetcher.py` | the fetch layer with a fake transport |
| `tests/integration/test_polling.py` | polling, the interval, closing, 404, bad answers, the breaker, 429, chaining, what people see, admin controls |
| `e2e/find.spec.ts` | the jobs list, health and counts, axe in both themes |

## 6. Commit

```
feat(search): add job source adapters, the fetch layer and source health
```

## 7. Interview defense

- Why one module talks to the network, and what a unit test found in it.
- Why parsers are pure and skip what they cannot trust.
- How the circuit breaker works and why a missing board is not a source failure.
- Why rate limits live with the source and are enforced by the poll, not by whoever asks.
- Why who may see a job is decided on read.
- Why Greenhouse and Ashby have code but cannot be used.

## 8. Verified and not verified

Verified: all tests above; three single real requests (one per ATS) to learn and save the real response shapes.

Not verified: a live poll through the whole path. Nothing is enabled, so the real network has not been used by the poller. Lever needs your confirmation (C-34) and an admin to enable it. Also not verified: how the breaker and intervals behave over days, the load of a big Greenhouse board, that these three companies' boards stay public, a larger company list, a retention policy for fetched text (C-53), and how Remotive and Adzuna will fit (C-35).

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0011 and refreshes the registry. After you have read Lever's terms (C-34), an administrator records the review and enables it (`PATCH /api/v1/admin/sources/lever`, see the runbook). The first poll starts by itself. Then open Find jobs, plan a search naming Palantir, and the jobs appear. `GET /api/v1/admin/sources/lever/log` shows each fetch.
