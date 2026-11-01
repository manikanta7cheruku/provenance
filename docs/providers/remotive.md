# Provider: Remotive

| Field | Value |
|---|---|
| Role in Provenance | Remote jobs feed or API. Planned at 2.6 only if the owner decides the restriction below is acceptable |
| Official documentation URL | https://github.com/remotive-com/remote-jobs-api |
| API documentation URL | https://github.com/remotive-com/remote-jobs-api |
| Terms of service URL | The rules are stated in the API repository above. A separate website terms page could not be located |
| Privacy policy URL | Not read |
| Authentication documentation URL | None needed |
| Rate limits | Advised at most 4 requests a day. More than 2 requests a minute are blocked |
| Data restrictions | Jobs are delayed by 24 hours. Remote jobs only. The `description` is HTML |
| Permitted use | `GET https://remotive.com/api/remote-jobs` with `category`, `company_name`, `search` and `limit` |
| Prohibited use | Do not send the jobs to third party job sites (Jooble, Neuvoo, Google Jobs and LinkedIn Jobs are named). Do not display jobs in order to collect sign-ups or email addresses |
| Required attribution | Link back to the Remotive job URL and name Remotive as the source. Failure may end API access |
| Data retention requirements | None stated |
| Capability class | AUTHORIZED_API (public) |
| Current integration status | Recorded as `restricted`, not enabled, no adapter |
| Last reviewed date | 2026-11-02 |
| Reviewed by | Build assistant, from the official documentation |
| Next review due | When the owner decides (carryover C-35) |
| Notes | Provenance requires an account. Whether showing Remotive jobs to signed in users counts as displaying jobs to collect sign-ups is a decision for the owner, or a question to ask Remotive. With four requests a day for the whole product the feed can only be a shared, cached copy |
