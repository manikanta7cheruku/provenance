# Provider: Lever postings

| Field | Value |
|---|---|
| Role in Provenance | Employer ATS public postings, read per company site. Planned adapter at checkpoint 2.6 |
| Official documentation URL | https://github.com/lever/postings-api |
| API documentation URL | https://github.com/lever/postings-api |
| Terms of service URL | https://www.lever.co/terms-of-service/ |
| Privacy policy URL | Not read |
| Authentication documentation URL | Same repository. Listing is shown without a key. A key is needed only to post applications |
| Rate limits | None stated for reading. Application posts above 2 per second get HTTP 429 (not used here). Lever may change limits without notice |
| Data restrictions | Only published postings are public. No full text search, no internal postings |
| Permitted use | The documentation says published postings are public and may be scraped by third parties. Hosts: `https://api.lever.co/v0/postings/{site}` and `https://api.eu.lever.co/v0/postings/{site}`. Filters: location, commitment, team, department |
| Prohibited use | The terms of service cover Lever's customers and do not mention the Postings API. They forbid competitors from accessing the service and reselling it. This product is not a competitor and never accesses customer accounts |
| Required attribution | None stated |
| Data retention requirements | None stated |
| Capability class | PUBLIC_DATA |
| Current integration status | Recorded as `verified` and not enabled. No adapter yet. Board `palantir` was confirmed to exist on 2026-11-02 |
| Last reviewed date | 2026-11-02 |
| Reviewed by | Build assistant, from the official documentation and terms. Owner confirmation pending (carryover C-34) |
| Next review due | 2027-04-30 (180 days) or on any change of the documentation |
| Notes | Poll each site no more than once an hour. Respect HTTP 429. The registry enforces the poll interval |
