# Source Compliance

Status: Unverified. No source below has been verified yet. This document defines the process and records the verification state. Statements about what a platform permits must come from its current official documentation and terms, read at integration time, not from memory, tutorials or forum posts.

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

| Source | Intended role | State |
|---|---|---|
| Greenhouse job boards | Employer ATS public board data | Unverified. Verify at 2.4, build at 2.5 |
| Lever postings | Employer ATS public postings | Unverified. Verify at 2.4, build at 2.5 |
| Ashby job boards | Employer ATS public postings | Unverified. Verify at 2.4, build at 2.5 |
| Remotive | Remote jobs feed or API | Unverified. Verify attribution and use limits at 2.4 |
| Adzuna | Job search API with key | Unverified. Verify coverage for target countries and terms at 2.4 |
| Company career pages | First-party | Per company. Check robots and terms before any fetch |
| LinkedIn | User import only | No automated access. Do not build any |
| Indeed, Wellfound, Naukri, Handshake | User import only unless an official integration is verified | No automated access assumed |
| GitHub | Candidate evidence via official API and OAuth | Unverified. Verify at 3.1 |
| LeetCode, CodeChef, GeeksforGeeks | Candidate evidence via user provided URL or export only unless an official API exists | Unverified. Verify at 3.1 |

### Open verification questions (2026-10-30)

- Which candidate sources cover India and early-career roles is unknown. Coverage is checked at 2.4 from official documentation.
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
