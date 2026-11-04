# Checkpoint 2.7: Deduplication, reversible links, private and public jobs, sightings

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.7-deduplication`. Decision: [ADR-0039](../adr/0039-deduplication-links-and-visibility.md). Runbook: [duplicates and links](../operations/runbooks/duplicates-and-links.md). Builds on the source registry ([2.5](checkpoint-2.5.md)) and the fetch layer ([2.6](checkpoint-2.6.md)).

## What this checkpoint is for
The same job often appears more than once: on a company's own board and again on another site, reposted under a new id, or pasted by you after the product already found it. Without this, a search shows the same job twice, you cannot tell the original from a copy, and any automatic merge is risky because a wrong merge loses information. This checkpoint recognises the same job in layers, shows it once, remembers everywhere it was seen, lets anyone undo a wrong link without losing anything, and keeps jobs you paste private while still telling you what public copies exist.

## 1. Build

**Matcher** (`pv_domain.dedupe`, no model). Four layers (same address, a repost on one board, same company and title and place with agreeing text, a very close title in the same place with nearly the same text), hard rules (different places, companies or levels are different jobs; missing text is never agreement), and a reason in words for every answer.

**Links and groups.** `source_job_links` holds an edge with method, score, reason and state (auto, suggested, confirmed, undone). Auto and confirmed edges form groups, worked out again whenever an edge changes, so undoing a link splits a group exactly where it should. Code never recreates or overrides a decision.

**Fetched jobs** gain normalised company and title (to find candidates), the group, and how many polls saw them. A board's company name is filled in from the company registry for sources that do not say.

**Search** shows one job per group, preferring the company's own career system, with "Also posted at" for the others. Copies from a source that is no longer usable are not listed.

**Private and public.** A pasted posting is compared with public jobs when it is read, and its decisions (`posting_links`, Row Level Security) are the person's alone. Public jobs never learn that a private posting exists.

**Screens.** Job page: **Where else this job appears** shows your copy and each public copy with its source, first and last seen, how often seen and a link to the original, plus every match with its reason and buttons: Same job, Not the same job, Decide again. Find jobs: "Also posted at" under a job.

**Admin.** `GET /admin/job-links` (by state) and `POST /admin/job-links/{id}/confirm|undo`, audited.

## 2. UX

- A match always says why in plain words, and any match can be undone and re-decided.
- Nothing about your pasted posting is shared. The page says so.
- When nothing matches it says that does not mean the job is not posted elsewhere.

## 3. Technical acceptance criteria

1. Each layer and each hard rule has tests. The same two postings always give the same answer, both ways round.
2. A job on two sources is grouped. A repost is linked. Different places, companies and levels are never linked. A suggestion joins nothing until confirmed.
3. Undoing a link splits a group only where that link was the only join. A re-run never recreates an undone link or overrides a decision.
4. Search shows one job per group and lists the others. A copy whose source stops being usable is hidden at once.
5. A pasted posting finds its public copies on read, including ones fetched later. Its decisions belong to its owner: other people get 404, other people's matches are unaffected, and decisions go with the posting when it is deleted.
6. No public table holds private content or a reference to a private posting. Decisions are protected by Row Level Security.
7. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the job page with matches, in light and dark. Match state is written as words. Each button names the job and the source it concerns. Each link to an original names its source.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_dedupe.py` | normalisers, layers, hard rules, groups and splitting |
| `tests/integration/test_dedupe_links.py` | the database: grouping, undo, search, privacy, Row Level Security, admin |
| `e2e/sightings.spec.ts` | the job page section, deciding, honest empty state, axe in both themes |
| `e2e/find.spec.ts` | "Also posted at" in the job list |

## 6. Commit

```
feat(search): add duplicate detection with reversible links and sightings
```

## 7. Interview defense

- Why matching is layered with hard rules and not one fuzzy score, and why a model does not decide.
- Why links are edges and groups are computed, so undo is a recomputation and loses nothing.
- Why a private posting is matched on read and the public side never stores a reference to it.
- Why the same title in two cities is two jobs.
- What was not proven: live cross-source matching, with only one source switched on.

## 8. Verified and not verified

Verified: all tests above with the real database. Cross-source matching with constructed jobs.

Not verified: matching on live data from two real sources (only Lever can be switched on, so there is one source so far), thresholds against real duplicates (carryover C-60), and name variants such as Bengaluru and Bangalore or Google LLC and Alphabet (C-62, C-63). The review of suggested links is an API, not a screen (C-64).

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0012. Paste a job in Opportunities, open it, and read "Where else this job appears". Once a source is polled, a pasted posting from the same company is matched against it. As an administrator, `GET /api/v1/admin/job-links?state=suggested` shows suggestions.
