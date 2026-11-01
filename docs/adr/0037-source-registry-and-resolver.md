# ADR-0037: Source registry, company registry and a deterministic resolver

Status: Accepted (checkpoint 2.5).

## Context
The next checkpoints fetch jobs from outside. The product promises never to claim it searched a platform it did not search, and never to touch a platform whose terms forbid it. Without a decision made first, the first adapter would be written against whatever API was easiest, and the rules would live in scattered `if` statements. Checkpoint 2.5 is therefore "source verification first": record the rules as data, read each candidate's official terms, and build the part that decides what may happen, before any fetching exists.

## Decision

**The source registry is data, not code.** Table `job_sources`, seeded from a versioned file (`registry_data/sources.json`), editable by administrators with an audit event for every change. It holds every field required by search-requirements.md: type, adapter, endpoint, capabilities, authentication, compliance status, where and when the terms were read and by whom, rate limit, quota policy, minimum poll interval, attribution text, geographic coverage, enabled switch, health counters and notes. Capabilities are explicit per source and never assumed to be uniform. The seed refreshes rows nobody has edited and never overwrites an administrator's edit.

**One rule decides whether a source may be used.** `enable_blocker` in `pv_domain.sources`: it must be verified, have a terms address and a reviewer, have been reviewed within the window (180 days, a setting), and not be import only. The database enforces the same rule as a CHECK, so a bug in the API cannot enable an unverified source. When the window passes, the source stops being usable at once, because the check runs on every plan, not only when it is switched on.

**Compliance is a status with four honest values.**
- `verified`: the terms were read and allow this use.
- `unverified`: not enough was read to say. Never rounded up to verified. Pages that could not be read are recorded as such.
- `restricted`: the terms allow some uses and the product's use needs a decision by the owner.
- `prohibited`: the terms forbid automated access. The platform is import only.

The verification record for every candidate is in [source-compliance.md](../compliance/source-compliance.md) and one provider file each. The result on 2026-11-02:

| Source | Status | Why |
|---|---|---|
| Lever postings | verified | Docs say published postings are public and may be scraped by third parties. Terms do not mention the API |
| Greenhouse job boards | unverified | Docs say the data is public, but the governing terms could not be located |
| Ashby job boards | unverified | Docs describe a public endpoint, the customer terms were not read in full |
| Remotive | restricted | Attribution, 4 requests a day, a ban on displaying jobs to collect sign-ups, and the product needs accounts |
| Adzuna | restricted | Personal use is allowed, commercial or lead generating use needs a licence, India coverage not confirmed from official pages |
| LinkedIn, Indeed, Wellfound | prohibited | Terms forbid scraping and automated access. Import only |
| Naukri | unverified | The terms page returned 403. Import only, nothing assumed |

A verification by the build assistant is recorded as such. It says it was read from official documentation and that the owner's confirmation is pending (carryover C-34, C-35). Nothing is enabled and no adapter exists.

**The resolver has no model.** `pv_domain.resolver.plan_search` turns an intent and the registry into a plan. For each source it returns one of three outcomes with a sentence made from the source's own record: `search` (verified, in date, switched on, with an adapter and a way to search or list), `import_required` (no permitted automated search, but the person can import jobs) and `unavailable` (with the reason, and the import path where there is one). A platform the person names that cannot be searched says so. It is never replaced silently. Companies are resolved separately, and a company's own career system is preferred when that source can be searched, then an aggregator that can filter by company, then import.

**Companies are resolved by code.** `pv_domain.company`: exact alias, then normalised name (case, punctuation and legal suffixes removed), then trigram similarity. A close spelling is accepted only when one company is clearly ahead. A name that merely starts the same (Tata) is offered as candidates for the person to pick. Nothing is guessed. A model never chooses a company.

**The model has one small job.** A typed sentence becomes a structured intent in one validated call (class L). Code cleans the answer: values outside the allowed lists are dropped with a note and the rest is kept. Work authorization is read from the profile and shown as such, never from the sentence. The sentence sits between random markers and the prompt says it is data. Searching by fields needs no model at all.

## Alternatives considered
- **Build the first adapter and check terms along the way.** Rejected: the order is the point. Terms found late would mean throwing code away or, worse, shipping it.
- **Let the model pick sources and companies.** Rejected: it cannot be tested and it can be talked into anything.
- **Hard-code the list of allowed platforms.** Rejected: terms and coverage change. A registry with expiry makes "no longer permitted" a data change with an audit trail.
- **Mark Lever, Greenhouse and Ashby all verified because they are public by design.** Rejected: "public" is not the same as "the terms say third parties may read it". Only what was read is marked.

## Consequences
- Until the owner confirms records and 2.6 builds adapters, every plan says "no source can be searched automatically" and offers import. That is the correct statement today.
- Remotive and Adzuna each need a decision from the owner before they can be used.
- The company list is a small seed (24 companies, three with confirmed board ids). It grows by data, and an administrator edit protects an entry from the seed.
- The review window turns every verification into a recurring chore.

## Evidence
Unit tests for the rules, the seed files, company resolution, intent cleaning and the resolver, including every example in search-requirements.md without a model. Integration tests against the real database for the seed, the CHECK that refuses to enable an unverified source, the plan, the sentence parser with a stand-in model, injection handling, the profile-only authorization, and the admin controls with audit. Browser tests for the Find jobs page with accessibility checks in both themes.
