# Provider: Greenhouse job boards

| Field | Value |
|---|---|
| Role in Provenance | Employer ATS public job board data, read per company board. Planned adapter at checkpoint 2.6, only after the terms are confirmed |
| Official documentation URL | https://docs.greenhouse.io/job-board.html |
| API documentation URL | https://docs.greenhouse.io/job-board.html |
| Terms of service URL | Not located. The guesses tried (greenhouse.com/legal/terms-of-use) returned not found |
| Privacy policy URL | Not read |
| Authentication documentation URL | Same page. GET needs no authentication. Only submitting an application needs HTTP Basic auth with an API key |
| Rate limits | None stated in the documentation read |
| Data restrictions | The documentation says job board data is public. No restriction on third party use is stated there |
| Permitted use | Reading published jobs per board: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs` (list, with `content=true` for full text) and `/jobs/{id}` |
| Prohibited use | Not stated in the page read. This product never submits applications |
| Required attribution | None stated |
| Data retention requirements | None stated |
| Capability class | PUBLIC_DATA |
| Current integration status | Recorded in the registry as `unverified`, not enabled, no adapter. Board `stripe` was confirmed to exist on 2026-11-02 |
| Last reviewed date | 2026-11-02 |
| Reviewed by | Build assistant, from the official documentation |
| Next review due | When the owner reads the governing terms (carryover C-34), and at most every 180 days after |
| Notes | Stays unverified because the terms of use could not be read. If they allow third party reading of published boards, mark it verified in Admin, and 2.6 may build the adapter |
