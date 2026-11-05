# Runbook: the GitHub connection

## Set it up (once, the operator)
1. Create an OAuth app at https://github.com/settings/developers. Callback URL: `<PUBLIC_BASE_URL>/connect/github/callback`. Do not enable Device Flow. Do not select scopes.
2. Put `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`. Restart: `.\scripts\pv.ps1 up`.
3. Open Profile. The GitHub panel should offer Connect GitHub. If it says "not set up on this server", the id or secret is empty or the stack was not restarted.

## "GitHub was not connected" after returning from GitHub
- "did not match the one that was started, or it took too long": the person waited over ten minutes, opened the link twice, or started again in another tab. They start again.
- "did not accept that sign-in": the callback URL in the OAuth app does not match `<PUBLIC_BASE_URL>/connect/github/callback` exactly, or the client secret is wrong. Check both. The API log shows `GITHUB_INVALID_CODE` with no secrets.
- "could not be reached": GitHub or the network. Nothing was stored. Try again.

## "The last read did not work"
- "Connect GitHub again": GitHub no longer accepts the token (the person revoked it, or the application secret was rotated). They disconnect and connect again. Nothing is lost: their entries stay.
- "asking us to wait": GitHub's rate limit. The task retries on its own (up to four attempts). If it keeps failing the person sees the message and can press Read my repositories again later.
- Stuck on "Reading your repositories": check the worker is running (`.\scripts\pv.ps1 status`) and the task list in Admin. See [stuck-task](stuck-task.md).

## A person says their entries are missing or changed
- Entries come only from repositories the person ticked. Open Profile, GitHub, and check the ticks. Unticking a repository removes its entry unless the person edited it (an edited entry stays and becomes theirs).
- A repository that was deleted or made private on GitHub disappears from the list on the next read, with its untouched entry.

## Rotating the application secret
All stored tokens stop opening. Every connection then shows "Connect GitHub again". This is by design. Tell people before you do it.

## A token may have leaked
Disconnect the person (or have them do it): the token is deleted and revocation is asked. Revoke the whole app's tokens from the OAuth app page on GitHub if many may be affected. The token is never in logs or audit records, so check where it could have been copied (a database backup, a screenshot).

## What to look at
- Audit events: `github.sign_in_started`, `github.connected`, `github.repos_chosen`, `github.disconnected` (no token, no repository names).
- Task type `sync_github` in the task list.
- The three tables are tenant data with Row Level Security. Never query them without a tenant.
