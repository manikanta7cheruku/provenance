# Checkpoint 2.5: Source verification, registries and the resolver

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.5-source-verification`. Decision: [ADR-0037](../adr/0037-source-registry-and-resolver.md). Records: [source-compliance.md](../compliance/source-compliance.md) and one file per provider in [providers/](../providers/README.md). Runbook: [sources and search planning](../operations/runbooks/source-registry-and-search.md). Requirements: [search-requirements.md](../product/search-requirements.md).

This checkpoint does no fetching. It decides, before any adapter exists, what the product may fetch, from where, and how it will say so. The terms of every candidate source were read from official pages and recorded, the registry and the resolver were built, and a person can see the result on a new Find jobs page.

## 1. Build

**Terms read and recorded.** Greenhouse, Lever, Ashby, Remotive and Adzuna (candidate feeds) and LinkedIn, Indeed, Wellfound and Naukri (import only), all on 2026-11-02, from official pages. What could not be read is recorded as not read: Greenhouse and Ashby governing terms, the Naukri page (HTTP 403), the rest of Indeed's terms, and Adzuna's country list.

**Source registry** (`job_sources`, migration 0010). Every field of search-requirements.md section 5, a seed file, a CHECK that refuses to enable a source unless it is verified, reviewed, in date, with a reviewer and not import only, and admin routes (`GET` and `PATCH /admin/sources`) that run the same rule and write an audit event. A setting (`SOURCE_REVIEW_WINDOW_DAYS`, 180) says how long a review stays valid.

**Company registry** (`companies`). 24 companies with aliases, domain and, for three whose board ids were confirmed to exist, the ATS and board.

**Resolver** (`pv_domain.resolver`). For every source: `search`, `import_required` or `unavailable`, with the sentence and the reason. For every company: first party, aggregator, import, or "which one did you mean". The copy comes from the source record and never claims a platform was searched when its jobs were supplied by the person.

**Search intent** (`pv_domain.search_intent`, `pv_llm.search_intent`). A typed sentence becomes a structured intent in one model call, then code cleans it: bad values are dropped with a note, countries come from a lookup, and work authorization comes from the profile only. A search can also be made from fields with no model.

**API and screen.** `GET /search/sources`, `POST /search/plan`, and a **Find jobs** page: type a sentence or fill in details, see what was understood, where it can go (searched, import needed, unavailable) with reasons, the company choices, and a list of every source with where its terms were read and a link to them.

## 2. UX

- "No source can be searched automatically for this yet. You can import jobs and we will analyze them." is the headline today, and it is true.
- Every source has a status written out, never color alone, a reason, and a link to its terms.
- A company that is not clear is put back to the person with buttons to choose.
- Searching by sentence says so plainly when the AI service is not set up, and the fields still work.

## 3. Technical acceptance criteria

1. Every example in search-requirements.md section 3 produces a deterministic plan in a unit test with no model.
2. A source cannot be enabled unless it is verified, reviewed in the window, and has a reviewer, in code and as a database CHECK. Admin edits are audited and refused next to the field.
3. A platform that cannot be searched is never substituted silently. Import stays available.
4. An expired review makes a source unavailable in the next plan.
5. Company resolution is deterministic: alias, normalised name, then close spelling only when one company is clearly ahead. Two close names are put back to the person.
6. A model answer that is odd is cleaned, with notes, and never trusted. Work authorization is never read from the sentence. Text in the sentence cannot close its own markers.
7. Nothing in the seed is enabled and nothing has an adapter. What was not read is not marked verified.
8. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the Find jobs page, empty and with a plan and a company choice, in light and dark. Status is text. The company choice is a labelled group. The terms links say which source they belong to.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_source_registry.py` | the rules, the seed files, company resolution, intent cleaning, the decision table, the examples |
| `tests/integration/test_search.py` | the seed and its CHECK, the plan, the sentence parser, injection, admin controls and audit |
| `e2e/find.spec.ts` | the page, the plan, company choice, fields, no key, axe in both themes |

## 6. Commit

```
feat(search): add the source registry, company registry and search resolver
```

## 7. Interview defense

- Why verification comes before the first adapter.
- Why compliance has four values, and why "public" is not the same as "permitted".
- Why capabilities are per source, and how the resolver turns them into three outcomes.
- Why company resolution is code, how the thresholds work, and why a prefix match is only a candidate.
- How the review window turns terms into data that expires, and why the database repeats the rule.
- What the model does in a search (one parse) and what it must never do.

## 8. Verified and not verified

Verified: all tests above, with the real database and a stand-in model.

Not verified: a real model parsing real sentences (carryover C-33), the owner's confirmation of the records (C-34), the decisions on Remotive and Adzuna (C-35), the unread terms (C-36), India coverage of Adzuna from an official page, a larger company list, how the page reads to a person, a screen reader session.

What the build assistant did not do: legal review. The records say what the pages said on 2026-11-02. They are not legal advice and they expire.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0010 and seeds the registries. Open Find jobs. Fill in a role and a company, press Plan with these details. With a Gemini key, type a sentence. As an administrator, `GET /api/v1/admin/sources` shows every record and what blocks enabling it.
