# ADR-0038: Source adapters, one fetch layer, and a circuit breaker

Status: Accepted (checkpoint 2.6).

## Context
Checkpoint 2.5 recorded what each source's terms allow and built the part that decides what may happen. Checkpoint 2.6 is the first code that talks to the outside. The risks are the ones the compliance record exists for: asking too often, ignoring "slow down", hammering a source that is failing, trusting what comes back, and showing jobs from a source that should no longer be used.

## Decision

**One module talks to the network.** `pv_worker.fetcher` is the only code that makes a request to a job source. It allows HTTPS only, to a host the adapter names, on the default port; follows no redirects; reads the answer as it arrives and stops at a size limit (25 MB, because a real Greenhouse board with full descriptions was 5.8 MB); has a connect and a read timeout; sends an honest User-Agent; and keeps no cookies or credentials between requests. A unit test found that the HTTP client kept cookies a source set, which broke the "no cookies" rule, so cookies are cleared after every request. Nothing a person types reaches this module: addresses are built from a fixed template and a board id from the company registry, checked against a plain-identifier pattern.

**Adapters are pure.** Each source has a parser in `pv_domain.job_feed` that turns its answer into one small record: id, https address, title, location, workplace, employment type, department, plain text description, dates, and a content hash. HTML is reduced to plain text (script and style dropped with their contents, escaped HTML decoded first because Greenhouse sends it escaped), addresses must be https with no spaces or quotes, and every field has a limit. A job that fails these is skipped and counted, never repaired. An answer that is not the expected kind at all is an error that counts against the source. Parsers were written against the official documentation and checked against one real answer per source read on 2026-11-02 (the saved, trimmed responses are the test fixtures).

**The rules of polite fetching are plain functions** (`pv_domain.fetching`), enforced by the poll task whoever asks:
- A board is not asked again before the source's minimum poll interval, kept per board in `source_targets`. A manual poll cannot get around it.
- One request at a time, with a gap between requests to the same host.
- 429 and Retry-After are obeyed (whole seconds only, capped at an hour).
- A **circuit breaker** per source: five failures in a row open it for 15 minutes, doubling up to six hours. While it is open nothing is requested. When the wait ends one request is the probe, and a failed probe opens it for longer. Other sources are never affected. A missing board (404) is that board's problem and does not count.
- Health words (unknown, healthy, degraded, down) are computed from the same counters, so what a person sees and what the breaker does cannot disagree.

**Only usable sources are polled.** Every poll first checks that the source is enabled, verified and in date, and has an adapter. If not, it logs a skip and does not schedule another. Enabling a source (an administrator action, refused unless verified) starts a self-scheduling chain of polls, with a key per slot as long as the interval so two chains become one.

**Fetched jobs are shared reference data** (`source_jobs`), kept in plain text. Jobs a complete listing no longer holds are closed, never deleted, and never from an answer that was in doubt (a bad or empty-by-skipping answer closes nothing). **Who may see a job is decided on read:** a job is listed only while its source is enabled, verified and reviewed within the window. Switching a source off or letting its review expire hides its jobs at once, without deleting them.

**Every attempt is logged** (`fetch_log`): board, outcome, status, size, counts, duration, and never any job text. The log is kept for 30 days.

## Which adapters, and why these
Lever, Greenhouse and Ashby have adapters. Lever is the only one verified, so it is the only one that can be switched on. Greenhouse and Ashby have code, tests and fixtures but stay unverified and unusable until their terms are read (carryover C-34): the registry, the database CHECK and the poll's own check all refuse to use them. Remotive and Adzuna have no adapter, because their terms need a decision first (C-35). No adapter exists for any import-only platform and none will.

## Alternatives considered
- **Build only the Lever adapter.** Rejected: the three parsers share one shape and one test method, and the gate keeps the other two dormant. Building them now means a verified status is the only thing missing later.
- **Fetch inside the API request.** Rejected: a poll takes seconds to minutes and must survive restarts. It is a worker task.
- **Scrape a company career page when no API exists.** Rejected: no verified terms, and not in the plan.
- **A queue-wide rate limiter only.** Rejected: the limit is a property of the source, so it lives in the registry and is checked by the fetch layer.
- **Delete jobs a board no longer lists.** Rejected: closing keeps history and makes the later duplicate and sighting work (2.7) possible.

## Consequences
- Until the owner confirms Lever (C-34) and enables it, nothing is fetched and every plan still says nothing can be searched. After that, one poll an hour per board at most.
- A Greenhouse board with full descriptions is megabytes per poll. That is acceptable at one poll an hour for a handful of boards and is recorded for review (C-52).
- The fixtures are one day's real shapes. A source that changes shape produces skipped jobs and failures, which the health words and the log show.
- Job text is stored. The terms read do not state a retention rule, so a policy is a carryover decision (C-53).

## Evidence
Unit tests for every parser against the saved real answers and hostile input, the rules of fetching, and the fetch layer with a fake transport (host and scheme limits, redirects, size, cookies, timeouts). Integration tests with the real database for a good poll, the interval, changes and closing, 404, bad answers, the breaker opening, probing and closing, 429 with Retry-After, network failure, unusable sources, chaining, what people can see, SQL filtering, hiding on expiry, and the admin controls with audit. Browser tests for the Find jobs page with accessibility checks.
