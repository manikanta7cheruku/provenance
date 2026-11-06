# ADR-0053: Observability, the Run Inspector and the Admin Console

Status: Accepted (checkpoint 3.5).

## Context
From 1.4 every workflow has a run, steps, model calls and a queue, and 2.x added sources with a circuit breaker. What was missing was the view that answers an operator's questions: is it healthy, why are jobs not appearing, is work stuck, what does it cost, is anyone abusing it. And a person whose run failed had a state and a technical line but no plain explanation. The risks are an admin console that quietly reads people's content, alerts that are noise or have no next step, numbers that look precise but were never measured, and a cost view that names accounts.

## Decision

**The console reads system tables only.** Tasks, worker heartbeats, model calls, job sources, the audit log and rate limit counters hold no one's content and have no Row Level Security. Runs, steps, plans and usage are tenant tables, and RLS has no admin exception (ADR-0023). So nothing in `pv_persistence.observability` touches a tenant table, and a test fails if its source ever names one. The console shows how the system is doing and can never show what anyone wrote.

**Alerts are rules over one snapshot, in the domain.** `pv_domain.alerts.evaluate(snapshot, thresholds)` is pure: database down, migrations behind, no worker, a stale queue (two levels), tasks past their lease, dead letters, a paused or failing source, model errors, spend against a ceiling, API server errors and slowness, failed sign-ins, wrong-origin requests. Each alert says what is wrong, what to do first, and where its runbook section is. The screen, the check command (`check-alerts`, exit 1 when anything is critical) and the tests all use the same function. A measurement that was not taken is `None` and fires nothing: the screen says "not measured", never "healthy".

**Thresholds are named, shown, and called starting points.** They sit in one dataclass and are printed on the Health page. They were chosen before there was traffic, and the page says they will be set from measurement (carryover). The one that needs a decision from the owner, a daily spend ceiling, is off until `LLM_DAILY_SPEND_CEILING_USD` is set, and the page says so.

**Request timings are in memory, per process.** A bounded window of status and duration (fifteen minutes, 5000 samples) gives the error rate and the median and slowest 5 percent. It holds no path, user or body. It describes the process that answered, and the screen says so. A store shared by every process comes with deployment.

**Cost is aggregate.** Model calls added up by model, by operation and by day for 7 or 30 days, with tokens, failures and estimated cost, plus how many accounts used it and what share the heaviest account made up. No account is named. Cost by plan is not shown, because the plan is in a tenant table (carryover).

**Find a run, from the system tables.** An admin pastes the reference a person quotes and sees the queue's tasks (type, state, tries, the redacted last error, the account) and the model calls for that run. Steps and what the run was about stay the person's.

**The person's Run Inspector explains itself.** The run page keeps its steps and model usage and adds: what the run was about with a link to it, a failure written as what happened and what to do (an unknown failure gets a safe generic sentence, never the raw class), totals (steps, calls, tokens, cost, models, prompt versions), plain step labels with the counts each step recorded (numbers only), and the reference to quote. It shows an operational trace, never reasoning and never the text of a job or resume.

**Health is one page of questions.** What needs attention (alerts), each part and its state, requests, work that is retrying or stuck (linking to the traced run), why jobs might not be appearing (each switched-on source), abuse and security in the last 24 hours (event counts and rate limits exceeded, nobody named), and how the alerts are decided. The queue, workers and dead letters stay on their own page.

## Alternatives considered
- **Prometheus and Grafana now.** Deferred: it needs deployment (3.7) and a decision on where metrics live. The in-process window and the system tables answer the same questions today.
- **An admin role that can read runs and steps.** Rejected: it breaks the boundary that makes the console safe to hand to an operator.
- **Push alerts (email, chat, pager) now.** Deferred: alerts need a channel the operator reads, which depends on deployment. Today they are on the console and in a command that can be run on a schedule.
- **Cost by plan and by account.** Deferred for plan (tenant data) and rejected for account (aggregate by default).
- **Break-glass access to content.** Not built: no admin route can read content, so there is nothing to break glass into.

## Consequences
- An operator can answer the six questions from one place and a person can read why their run failed.
- Request statistics reset when the API restarts and do not add up across processes.
- Alerts are only as good as their thresholds, which are guesses until traffic exists.
- Database connection, disk, replication and backup alerts wait for deployment.

## Evidence
Unit tests (32): every alert rule at its edge (just under, at, over), a missing measurement fires nothing, ordering and the runbook on every alert, request statistics (counts, percentiles, forgetting old requests, bounded memory), and the plain words for a run. Integration tests (22) with the real database: only an admin can ask, health shape and components, request timings measured, dead letter, stuck and retrying tasks, a paused source, security events and rate limit pressure without naming anyone, usage adding up and never naming a person, the spend ceiling, tracing a run from system tables alone, an unknown run, no tenant table in the console's source, the person's run with subject, failure, totals and plain steps, another person still gets 404, and the check command's exit codes. Browser tests (27) with axe in light and dark on every page and a phone.
