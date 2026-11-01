# Source Compliance

Status: Records made at checkpoint 2.5 (2026-11-02) from official pages. One source is verified, two are unverified, two are restricted, three are prohibited for automation and one could not be read. Nothing is enabled and no adapter exists. This document defines the process and records the verification state. Statements about what a platform permits must come from its current official documentation and terms, read at integration time, not from memory, tutorials or forum posts.

## 1. Verification record (required for each source)

| Field | Content |
|---|---|
| Access method | Official API, public feed, employer ATS endpoint, user import only |
| API or feed documentation URL | |
| Terms URL and date read | |
| Rate limits and quota | |
| Attribution requirements | |
| Permitted use and restrictions | |
| Authentication requirements | |
| Last verification date | |
| Verified by | |
| Next review due | |
| User import supported | |
| Notes | |

A source cannot be enabled without a completed record, and verification expires on a schedule.

## 2. Candidate sources and current state

State as recorded on 2026-11-02. The registry (`job_sources`) holds the same records, and each provider has a file in [providers/](../providers/README.md). "Read" means the page was read on that date. It is not legal advice, and every record expires after the review window (180 days).

| Source | Intended role | Status | What was read and what is open |
|---|---|---|---|
| Greenhouse job boards | Employer ATS public board data | Unverified | API documentation read: public, no authentication to read, no rate limit or attribution stated. The governing terms could not be located. Owner to read (C-34) |
| Lever postings | Employer ATS public postings | Verified (owner confirmation pending, C-34) | API documentation and terms of service read: postings are public and may be scraped by third parties, terms do not mention the API. No rate limit for reading |
| Ashby job boards | Employer ATS public postings | Unverified | API documentation read: public endpoint, no authentication, no rate limit stated. Customer terms found, not read in full. Owner to read (C-34) |
| Remotive | Remote jobs feed or API | Restricted | Official API repository read: attribution required, 4 requests a day advised, 24 hour delay, no redistribution to other job sites, no displaying jobs to collect sign-ups. Owner decision (C-35) |
| Adzuna | Job search API with key | Restricted | Official terms read: personal use allowed, commercial or lead generating use needs a licence, attribution required, no numeric limits. India coverage not confirmed from official pages. Owner decision (C-35) |
| Company career pages | First-party | Unverified | Per company. robots.txt and terms before any fetch |
| LinkedIn | User import only | Prohibited for automation | User Agreement read: forbids bots, scraping and automated access |
| Indeed | User import only | Prohibited for automation | About 200,000 of 349,000 characters read: forbids scraping the sourcing database and automating apply. Rest to be read (C-36) |
| Wellfound | User import only | Prohibited for automation | Terms read: forbid copying content, scraping and excess automated access |
| Naukri | User import only | Unverified | Terms page returned HTTP 403, not read. No automation assumed (C-36) |
| GitHub | Candidate evidence via official API and OAuth | Unverified | Verify at 3.1 |
| LeetCode, CodeChef, GeeksforGeeks | Candidate evidence via user provided URL or export only unless an official API exists | Unverified | Verify at 3.1 |

### Open verification questions (2026-10-30)

- Which candidate sources cover India and early-career roles is unknown. Coverage is checked at 2.5 from official documentation.
- No Indian job platform has been verified to offer a permitted feed. None is assumed to. User import remains the path for platforms without a verified integration.
- A browser extension that sends a page the user is viewing to the product is under consideration. Each target site's terms must be read before it is built. No decision is made.

## 3. Rules

1. No scraping of any platform that does not authorize it.
2. No bypassing authentication, CAPTCHAs, anti-bot systems, rate limits, paywalls or robots restrictions.
3. No browser fingerprint spoofing, proxy rotation, CAPTCHA solving, credential sharing or automated login.
4. User import of data the user collected themselves is supported for every platform.
5. Source and acquisition method are stored separately and shown honestly.
6. Terms are re-checked on the schedule in the registry.

## 4. Provider documents

Each provider has a file in `docs/providers/` using the template there. See [providers/README.md](../providers/README.md).
