# Checkpoint 3.1: The GitHub connection

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.1-github-connector`. Decision: [ADR-0049](../adr/0049-github-connection.md). Provider notes: [GitHub](../providers/github.md). Runbook: [GitHub connection](../operations/runbooks/github-connection.md). Builds on the profile ([1.6](checkpoint-1.6.md)), evidence search ([1.7](checkpoint-1.7.md)) and the worker ([1.4](checkpoint-1.4.md)).

## What this checkpoint is for
A person's best evidence is often public work on GitHub. This checkpoint lets them connect GitHub, choose repositories, and have each become an editable project entry that jobs are checked against. It also gives an honest path for evidence on platforms that cannot be connected.

## 1. Build
- **Connect GitHub** with OAuth asking for **no permissions** (public information only), PKCE and a single-use state. The screen says so before the person connects.
- **Encrypted tokens** (AES-256-GCM, bound to the person) and **one gateway** to GitHub with a host allowlist, no redirects, size caps and plain failure codes.
- **Choose repositories:** up to 100 public repositories are listed and six are suggested. The person ticks up to twelve.
- **Repositories as evidence:** each chosen repository becomes a project entry marked "From GitHub". Re-reading refreshes untouched entries, never overwrites an edit, and removes entries whose repository is gone or unchosen.
- **Disconnect:** deletes the token, asks GitHub to revoke it, removes the entries (or keeps them as the person's own), and says honestly whether GitHub confirmed.
- **Other platforms:** a list of places that cannot be connected, why, and what to do instead.
- Data: migration 0018 (`github_connections`, `github_oauth_states`, `github_repos`, and `github` allowed as an entry source). Routes under `/api/v1/github`. A worker task `sync_github`. A new package `pv_github`. `cryptography` is a new dependency.
- Settings: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (empty means off), and operator-only base addresses.

## 2. UX
- The Profile page has a GitHub panel. It says what is asked, what is read and how to leave, before the Connect button.
- The return from GitHub is a short "Connecting GitHub" page that clears the code from the address bar.
- Every failure says what to do: declined, expired, refused, not set up on this server, GitHub unreachable, connect again.
- The repository list is a checkbox group with a description, language, stars and a "Suggested" note, and a limit message.
- Disconnecting asks first and says what will happen.

## 3. Technical acceptance criteria
1. No scope is ever sent to GitHub and the database refuses a stored scope.
2. A sign-in return is accepted once, only for the person who started it, within ten minutes, and the state is checked before GitHub is asked for anything.
3. A stored token is sealed, is not in any response, log or audit record, opens only for its owner, and a changed or moved token is refused.
4. The gateway never contacts another host, never follows a redirect, caps what it reads and refuses names that could change an address.
5. Text from a repository is cleaned and capped, and an entry made from it passes the same checks as one a person types.
6. Nothing becomes evidence until chosen, at most twelve, only the person's own listed repositories.
7. An entry the person edited is never overwritten by a re-read.
8. Disconnecting deletes the token even when GitHub does not confirm the revoke.
9. Without an OAuth app configured the feature is off and says so.
10. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on the panel not connected, connected with repositories and a failed read, and the disconnect question, in light and dark, and nothing scrolls sideways at 390 pixels. The repository list is a fieldset with a legend and each repository is a labelled checkbox with its description. Status is text and a shape.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_secretbox.py` | encryption (7) |
| `tests/unit/test_github_rules.py` | the rules (16) |
| `tests/unit/test_github_gateway.py` | the gateway against a mock transport (16) |
| `tests/integration/test_github_connection.py` | the database, API and worker with a test double (26) |
| `e2e/github.spec.ts` | the screen and the return page in the browser, axe in both themes (18) |
| `src/features/profile/profile.test.tsx` | the "From GitHub" label |

## 6. Not verified
A real connection to github.com (it needs an OAuth app created by the owner, C-120), GitHub's behaviour under real rate limits, real READMEs in the wild, a screen reader pass, and the application secret being rotated in production.

## 7. What is next
3.2, career preparation, which reuses the evidence and the grounded generation built so far.
