# Provider: GitHub

| Field | Value |
|---|---|
| Role in Provenance | Candidate evidence: a person connects their GitHub account, chooses public repositories, and each becomes an editable project entry in their profile. |
| Official documentation URL | https://docs.github.com |
| API documentation URL | https://docs.github.com/en/rest |
| Terms of service URL | https://docs.github.com/en/site-policy/github-terms/github-terms-of-service |
| Privacy policy URL | https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement |
| Authentication documentation URL | https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps |
| Rate limits | A request made with a person's OAuth token counts against that person's primary limit of 5,000 requests an hour (shared with their other tokens). Exceeding it returns 403 or 429 with `x-ratelimit-remaining: 0` and `x-ratelimit-reset`. Secondary limits return 403 or 429 with `retry-after`. We make at most one list call and one README call per chosen repository (at most 13 requests) per read, and never read more often than the person asks. |
| Data restrictions | Terms section H: the API may not be used to download data for spam, including selling GitHub users' personal information (recruiters and job boards are named as examples). Tokens may not be shared to get around rate limits. All use is subject to the GitHub Privacy Statement. |
| Permitted use | A product acting for a person, with their authorization, on that person's own data. |
| Prohibited use | Selling or sharing GitHub users' personal information, bulk collection of other people's data, sharing tokens to evade limits, abusive request volumes. |
| Required attribution | None required for the API. Entries made from a repository are labelled "From GitHub" in the product. |
| Data retention requirements | None stated for this use. We keep the access token only while the connection exists (deleted on disconnect, on deleting the account, and the connection is removed with the person). We keep public facts about the chosen and listed repositories and a plain excerpt of each chosen README so the person can see and edit them. |
| Capability class | OAUTH_INTEGRATION |
| Current integration status | Built and tested against a test double (checkpoint 3.1). Not yet exercised against github.com: it needs an OAuth app created by the operator (carryover C-120). |
| Last reviewed date | 2026-11-05 |
| Reviewed by | Claude (read from the pages above, not from memory). The owner confirms at the end of the build (carryover C-120). |
| Next review due | 2027-05-05 |
| Notes | See the decisions below. |

## What we ask for

**No OAuth scope at all.** With no scope, GitHub gives read access to public information only. Private repositories, organisation data, e-mail addresses and every write action are out of reach by construction, not by promise. A scope can be added only by editing one constant (`OAUTH_SCOPE` in `pv_domain.github`) and the database refuses any scope other than empty (`CHECK (scope = '')`), so it cannot widen by accident. We also use PKCE (`S256`) and a random single-use `state`.

## What we read

- the person's login and id (`GET /user`)
- their public repositories (`GET /users/{login}/repos?type=owner`), at most 100 per read
- the README of each repository the person chose (`GET /repos/{owner}/{repo}/readme`), at most 16,000 bytes

## What we do not do

Read private repositories, read other people's repositories, read code, issues, commits or e-mail addresses, write anything to GitHub, or call GitHub while analysing a job. Analysis uses only what is already stored in the profile.

## Token life

GitHub OAuth tokens are long-lived unless the app opts in to expiry. We store the token sealed (AES-256-GCM, bound to the person, see ADR-0049) and delete it on disconnect, after asking GitHub to revoke it (`DELETE /applications/{client_id}/token`). If GitHub does not confirm, the product says so and tells the person where to remove the app (github.com/settings/applications). A person can also revoke from GitHub at any time, after which the next read fails with "connect GitHub again".

## Setup (the operator)

1. Create an OAuth app at https://github.com/settings/developers.
2. Homepage URL: your public address. Authorization callback URL: `<PUBLIC_BASE_URL>/connect/github/callback` (for local use `http://localhost:5173/connect/github/callback`).
3. Put the client id and secret in `.env` as `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`. Restart the stack.
4. Leave "Enable Device Flow" off. Do not tick any scope anywhere.
