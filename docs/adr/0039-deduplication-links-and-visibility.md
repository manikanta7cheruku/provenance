# ADR-0039: Deduplication with reversible links, private and public jobs, and sightings

Status: Accepted (checkpoint 2.7).

## Context
The same job reaches the product in more than one way: on a company's own board and again on another site, reposted under a new id, and pasted by a person after the poller already found it. Without a decision, a search shows the same job two or three times, a person cannot tell which copy is the original, and any rule that merges jobs is a data-loss risk the moment it is wrong. There is also a privacy line to protect: jobs fetched from sources are public, while a posting a person pastes belongs to them.

## Decision

**Matching is layered, rule based and explainable** (`pv_domain.dedupe`, no model). Strongest first, and a stronger layer wins:
1. **The same address**, after tracking noise is removed.
2. **The same source and board, the same content under a new id**: a repost.
3. **The same company and title in the same place with agreeing text.** The text must agree by a share of five-word runs. With no text to compare, the link is only suggested.
4. **A very close title in the same place with nearly the same text.**

Hard rules no score overrides: two postings in different places are different jobs (the same title in two cities is two jobs), different companies are never linked, a different level in the title ("Senior") is a different job, and a missing place or missing text is never read as agreement. The result is `auto` (linked at once), `suggested` (a person or administrator decides) or no match, with a reason in plain words ("Same company, title and place, and 92% of the wording matches").

**Links are edges and groups are computed from them.** A link between two fetched jobs is a row (`source_job_links`) with a method, a score, a reason and a state: `auto`, `suggested`, `confirmed` or `undone`. Auto and confirmed links join jobs into a group (`group_id`, the smallest id in the connected set). **Undoing a link removes that edge and works the groups out again**, so a group splits exactly where the link was the only join, and nothing is lost: the jobs, the edge and who undid it all remain. Code only creates missing edges, so an undone link is never made again, and a decision is never overridden by a later comparison.

**Private and public are separate sides.**
- *Public:* fetched jobs are shared reference data. Their links and groups are visible to everyone in the form of "also posted at", and administrators may confirm or undo them (audited).
- *Private:* a pasted posting stays tenant data under Row Level Security. It is compared with public jobs **when it is read**, never stored as a link, so a job fetched after the paste is found and nothing goes stale. Only the person's decisions ("same job", "not the same job") are stored (`posting_links`, with Row Level Security), and they affect nobody else. **Public jobs never learn that a private posting exists:** no public row refers to it, and the comparison reads the private posting only in the owner's own request.
- Only jobs from sources that may be used right now are considered, on both sides. When a source stops being usable its copies disappear from matches and from "also posted at" at once.

**Search shows one job per group.** The job shown is the one from the company's own career system when there is one, otherwise the one seen first. The other copies are listed under it ("Also posted at ..."). Filters apply before grouping, so a group appears when any member matches.

**Sightings are kept as facts, not a log.** Each fetched job keeps when it was first and last seen and how many polls saw it. A posting's sightings are the person's own copy ("Pasted by you") plus every public copy in the groups linked to it. Closed copies are shown as no longer listed. A full history of every sighting is not kept, because the fetch log already records each poll and a per-job history would multiply storage for no decision it supports.

## Alternatives considered
- **A fuzzy score alone decides.** Rejected: one number cannot explain itself, and "the same title in two cities" scores very high. Layers with hard rules can be tested case by case.
- **A model decides whether two postings match.** Rejected: not repeatable, not testable against a fixed list of cases, and the product's rule is that code decides what is stored as true.
- **Merge duplicates into one row.** Rejected: it destroys information and cannot be undone. Edges and groups can.
- **Store the private link and expose it to the public job.** Rejected: it would reveal that someone saved a job. Matching private against public on read keeps the public side blind.
- **Compare every job with every other.** Rejected: candidates are found by normalised company first (indexed), capped at 400.

## Consequences
- Dedupe quality depends on the normalisers. Company names are matched after case, punctuation and legal-suffix normalisation only, so "Google LLC" and "Alphabet" are different until a company alias is added to the registry. Places are compared by words and country names, so "Bengaluru" and "Bangalore" are treated as different places. Both are recorded as carryover.
- Nothing is linked across companies, ever. That favours missing a duplicate over merging two different jobs.
- With only Lever switched on there is one source, so cross-source matching has been proven on constructed data and not yet on live data (carryover).
- The administrator review is an API for now. A screen for it is not part of this checkpoint.

## Evidence
Unit tests for every normaliser, every layer and rule, symmetry, determinism, and group computation including splitting. Integration tests with the real database: a job on two sources is grouped, a repost is linked, different places, companies and titles are not, a suggestion joins nothing until confirmed, a decision is never overridden by a re-run, search shows one job with the others listed and hides a copy whose source stopped being usable, the admin confirm and undo with audit and a chain split, a pasted posting's matches with reasons, a person's decisions (undo, confirm, reset), privacy between people, that public rows never contain private content, Row Level Security on decisions, cascade on delete, and expiry of a source removing its matches. Browser tests with accessibility checks in both themes.
