# Provider: Ashby job boards

| Field | Value |
|---|---|
| Role in Provenance | Employer ATS public job postings, read per company board. Planned adapter at checkpoint 2.6, only after the terms are confirmed |
| Official documentation URL | https://developers.ashbyhq.com/docs/public-job-posting-api |
| API documentation URL | https://developers.ashbyhq.com/docs/public-job-posting-api |
| Terms of service URL | https://www.ashbyhq.com/terms (the Customer Terms of Service, a contract with Ashby's customers) |
| Privacy policy URL | Not read |
| Authentication documentation URL | Same page. No authentication is mentioned for the public endpoint |
| Rate limits | Not specified in the documentation |
| Data restrictions | Fields missing in Ashby are missing in the response |
| Permitted use | `GET https://api.ashbyhq.com/posting-api/job-board/{board_name}`, optional `includeCompensation=true`. Fields include title, location, department, workplace type, employment type, descriptions, job and apply URLs |
| Prohibited use | Not stated on the page read. The customer terms were found by search and not read in full |
| Required attribution | None stated |
| Data retention requirements | None stated |
| Capability class | PUBLIC_DATA |
| Current integration status | Recorded as `unverified`, not enabled, no adapter. Board `ramp` was confirmed to exist on 2026-11-02 |
| Last reviewed date | 2026-11-02 |
| Reviewed by | Build assistant, from the official documentation |
| Next review due | When the owner reads the terms (carryover C-34) |
| Notes | The endpoint is described as public, but whether third parties may read it is not settled by the pages read, so it is not marked verified |
