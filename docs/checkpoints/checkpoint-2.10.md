# Checkpoint 2.10: The shortlist email and application drafts

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.10-shortlist-and-drafts`. Decision: [ADR-0042](../adr/0042-shortlist-email-and-application-drafts.md). Runbook: [shortlist and drafts](../operations/runbooks/shortlist-and-drafts.md). Builds on the workbench ([2.9](checkpoint-2.9.md)), the evidence check ([1.9](checkpoint-1.9.md)), tailoring ([2.4](checkpoint-2.4.md)) and the mail queue ([1.4](checkpoint-1.4.md)).

## What this checkpoint is for
Two things close the loop from "I found a good job" to "I applied". A person should be reminded of the few jobs worth their time without opening the product, and when they decide to apply they should not start from a blank page. Both must stay honest: the email says why each job is there and never repeats itself, and a draft only says what the person's own evidence supports, always says it is a draft, and is never sent anywhere.

## 1. Build

**Shortlist email.** Settings, Shortlist email. Off until turned on, daily or weekly, an hour, the person's own time zone, up to 10 jobs. Goes only to a verified address. A deterministic selection (open jobs with a finished check, a Strong or Good fit, nothing in the way, never sent before) ranked by fit, clarity of eligibility, saved before new, newest, with the reason for each job. A preview shows exactly what would be sent now. "Send me one now" queues one. The history says what happened each time: sent, nothing to send, not sent because the address is not verified, or could not be sent. The task arranges its own next run, ignores a time that is no longer the next one, and cannot send a time twice. Plain text with links into the product only.

**Application drafts.** On the job page, Application drafts. A cover note (one per job) and answers to common questions or the person's own, up to 8 per job, for a job whose evidence check is finished. Written from the evidence that supported the job's requirements. Every number, name, tool and word the job asked for is checked against that evidence and the job heading, and the ones that are not found are named for the person. The text is the person's to edit, and every edit is checked again. Copy, write again (asks first when the person edited), delete. Always labelled as a draft. Nothing is sent anywhere.

**Tracker polish.** Applications show how long ago each was made, and the pane points to the drafts.

**Data.** Migration 0015: `application_drafts`, `shortlist_settings`, `shortlist_runs`, `shortlist_items` (Row Level Security, forced). Worker tasks `draft_application` and `send_shortlist`. Routes: `GET|POST /jobs/{id}/drafts`, `PUT|DELETE /jobs/{id}/drafts/{draft_id}`, `GET|PUT /shortlist`, `GET /shortlist/preview`, `POST /shortlist/send`. A shared loader (`pv_persistence.workrows`) gives the workbench and the shortlist the same eligibility and fit for every job.

## 2. UX

- A draft says it is a draft every time, in the same words, and says nothing is sent.
- Unsupported claims are listed in the person's words ("kubernetes (a name or tool)") with what to do, and clear as soon as they are removed.
- The settings say what would be sent and when, and the preview shows the reasons. An empty preview says what a job needs.
- Nothing is sent when there is nothing worth a look, and the history says so.

## 3. Technical acceptance criteria

1. The next time is on the person's own clock, strictly after now, never more than a week and a day away, and keeps the local hour across a change of clocks. A time that does not exist or happens twice has a defined result.
2. The same jobs always give the same shortlist, whatever order they arrive in. A job that was sent, dismissed, applied for, not checked, below Good, or ruled out is never in it.
3. A due time is handled once. A retried task sends nothing twice. A task for a time that is no longer the next one does nothing. Mail trouble does not end the schedule. A late worker does not send a pile.
4. The email goes only to a verified address, is read from the account (never from a task), and holds only the person's own jobs.
5. A draft is made only from the supported evidence of a checked job. With none, the model is not asked. Every claim is checked and the unsupported ones are stored and shown. The check runs again on every edit.
6. Writing a draft again never throws away edits unless the person agrees. An older or deleted task does nothing.
7. Drafts, settings, runs and history belong to their owner (Row Level Security), go with the job and the person, and are audited without their text or the address.
8. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on a job page with drafts that are working, ready (with the evidence open), carrying a warning, and with the write-again confirmation open, nor on the shortlist settings with the preview and the history, in light and dark. The draft label is text. Claims are listed as words. Every button names the draft it acts on.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_shortlist.py` | schedule cleaning, next time and zones, selection and ranking, reasons |
| `tests/unit/test_draft_rules.py` | draft claims, questions, the prompt, the email text |
| `tests/integration/test_drafts.py` | the database: drafts end to end, editing, privacy |
| `tests/integration/test_shortlist_email.py` | the database: schedule, selection, sending, retries, privacy |
| `src/features/opportunities/drafts.test.tsx`, `src/features/settings/shortlist.test.tsx` | the screens |
| `e2e/drafts-shortlist.spec.ts` | every draft state, the settings, axe in both themes |

## 6. Commit

```
feat(shortlist): add the shortlist email and grounded application drafts
```

## 7. Interview defense

- Why selection is deterministic and explained, and why a model never chooses what is emailed.
- How a scheduled email stays correct: its own clock, DST, a run unique per time, a task that arranges the next, one that ignores a stale time.
- Why at-least-once delivery means a rare duplicate and not a lost email, and why that is the right trade here.
- Why a draft shows its unsupported claims instead of blocking, while a resume change is blocked.
- Why the claim check is only a floor (what it cannot catch).
- What was not proven: a real model, a real inbox.

## 8. Verified and not verified

Verified: all tests above with the real database, a stand-in model and a stand-in mail server.

Not verified: drafts from a real model (and how often the claim check flags honest text), a real inbox (delivery, spam, how it reads), a send across a real change of clocks, and one-click unsubscribe. All are in the carryover register.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0015. Open Settings, turn on the shortlist email, preview it and press Send me one now (the worker log or the local inbox shows it). On a job whose evidence check is finished, write a cover note once a real model is set up (carryover C-01).
