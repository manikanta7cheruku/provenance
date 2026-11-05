# ADR-0049: The GitHub connection

Status: Accepted (checkpoint 3.1).

## Context
A person's strongest evidence is often public work on GitHub, and the profile has no way to use it. The roadmap asks for a GitHub connector (OAuth, least scope, encrypted tokens), repo content as evidence, and a path for platforms that cannot be connected. Connecting an outside account brings new risks: a sign-in that can be forged or replayed, a long-lived token to protect, a third party whose responses are untrusted, text written by strangers that ends up in a profile and in model prompts, and a promise about what we can and cannot see.

## Decision

**Ask GitHub for no permissions.** The OAuth request carries no `scope`. GitHub then grants read access to public information only. That is the least scope there is, and it means private repositories are not merely unused but unreachable. The constant is empty on purpose, the authorise address builder only adds a scope if it is non-empty, a test asserts none is sent, and the database refuses any stored scope (`CHECK (scope = '')`). The screen states the scope in a plain sentence before the person connects.

**A guarded sign-in.** The server creates a random `state` and a PKCE verifier, stores a hash of the state and the verifier sealed, and returns the GitHub address. The person goes to github.com and is sent back to the web app (`/connect/github/callback`), which posts the code and state to the API with the session and the CSRF token. The API takes the state first, once, for that person only, within ten minutes, and only then asks GitHub for anything. A state for another person, a used state, an expired state and a made-up state all give the same sentence and cost GitHub nothing. Starting again replaces the earlier sign-in. The web app removes the code and state from the address bar and history before doing anything else.

**The token is sealed.** An access token is encrypted with AES-256-GCM (`pv_config.secretbox`) before it is stored. The key is derived (HKDF-SHA256, a fixed purpose) from the application secret. A fresh random nonce is used for every seal, and the context ("github-token:" and the person's id) is authenticated as associated data. A stored token that was changed fails to open, and one copied to another person's row fails to open. The token is opened only inside the worker for the length of its calls, is never in an API response, a log line or an audit record, and the tests check each of those. Rotating the application secret invalidates stored tokens (people connect again), which is the safe failure.

**One door to GitHub.** `pv_github.HttpGitHubGateway` is the only code that talks to GitHub. It contacts only the two hosts the operator configured, refuses any other address before the request is made, never follows a redirect, has short timeouts, reads at most a fixed number of bytes, sends the token only in the `Authorization` header, validates the shape of every answer and the form of every name that goes into an address (a login or a `full_name` that could change the path is refused), and turns every failure into one of five plain codes. Raw answers and headers never reach a log or a screen. It is a protocol in the domain (`GitHubGateway`) so the API and the worker share it and tests use a double.

**Repository text is untrusted data.** Names, descriptions, topics and the README are written by someone else. They are cleaned (control and direction characters, tags and markup removed), capped, and a README is reduced to a few plain sentences with badges, images, links, code blocks and tables removed. What is stored is data for the person to read and edit. It is checked by the same rules as an entry the person types, so a repository can never put more into a profile than a person could. An instruction hidden in a README is text in a profile entry, like any other entry, and the evidence agent already treats entries as quoted material, never as instructions.

**Evidence, chosen by the person.** The sync lists up to 100 public repositories and suggests six (not forks, not archived, with a description, recent, some stars). Nothing becomes evidence until the person ticks it, at most twelve. Each chosen repository becomes a `project` entry with source `github` and a stable key (`github:<repo id>`), shown as "From GitHub". A re-read refreshes entries the person has not touched, never overwrites one they edited (the edit makes it theirs), removes the entry of a repository that is no longer chosen or no longer public, and hands an edited one to the person. A job is then checked against these entries exactly like any other entry. There is no live call to GitHub during analysis: the analysis uses what is stored.

**Leaving is complete.** Disconnect deletes the token, the pending sign-ins and the repository list, asks GitHub to revoke the token, and either removes the entries made from repositories or, if the person asks, keeps them as their own. The token is deleted whether or not GitHub confirms, and the screen says honestly whether it did. Deleting the account deletes everything through the foreign keys.

**Other platforms.** LinkedIn, Naukri, Wellfound and others do not allow automated reading. The screen lists them with why and what to do: export a PDF and upload it under Your resume (the entries are checked by the person), or add an entry by hand with its link. Nothing is fetched from those links.

**Off unless configured.** Without `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` the gateway is not built, the screen says GitHub is not set up on this server and offers nothing to click, and nothing else changes.

## Alternatives considered
- **Request `read:user` or `public_repo`.** Rejected: with no scope public data is already readable, and any scope is more than needed. `repo` (private repositories) was never considered.
- **A personal access token pasted by the person.** Rejected: it teaches people to paste secrets and cannot be revoked by the app.
- **Device flow.** Rejected for the web app: the redirect flow is simpler and the person is already in a browser.
- **Keep the token in plain text in the database.** Rejected: a database copy, a backup or a log would then be a working credential.
- **A key per person in a key store.** Deferred to deployment (carryover): one derived key with per-person context binding is enough for the build, and a managed key store (KMS) adds rotation without changing the format, thanks to the version prefix.
- **Read repositories live during analysis (an `inspect_github_repo` tool).** Rejected: it would put a third party in the middle of a verdict, make results unrepeatable, spend the person's rate limit, and let repository text reach a prompt unreviewed. The person reviews what becomes evidence.
- **Import every repository.** Rejected: most are noise, and it would bury the evidence that matters. Six are suggested and twelve is the limit.
- **Fetch the other platforms' pages.** Rejected on their terms (docs/compliance).

## Consequences
- Rotating the application secret disconnects every GitHub connection. People connect again, nothing else is lost.
- The first real connection needs an OAuth app created by the operator and has not been exercised against github.com (carryover C-120).
- A repository's README excerpt is a short summary, not a quote. The person can edit it.
- GitHub's rate limit is the person's own. We use a handful of requests per read and never poll.
- Contributions to other people's repositories, organisations, gists and pinned repositories are not read.

## Evidence
Unit tests: encryption (round trip, fresh nonce, context binding, tamper, another key, short key), the rules (no scope, S256 per RFC 7636, random state, expiry, text cleaning, README reduction, hostile repositories, suggestions), and the gateway against a mock transport (code exchange, header-only token, public-only listing with cleaning, unsafe names, capped README, no redirects, no other host, plain failure codes, no token in logs, revoke). Integration tests with the real database and a test double (26): forced Row Level Security and the empty-scope check, the sign-in (no scope, PKCE, sealed token, single use, only the starter, expiry, replacement), the sync (listing, suggestions, nothing is evidence until chosen, entries with their source, edits kept, refresh, removal, limits, hostile text), failure and retry, a sealed token moved to another person, ownership, disconnect (token deleted, revoke asked, entries removed or kept, deleted even when GitHub does not confirm), and the audit trail without token or repository text. Browser tests (18) with axe in light and dark.
