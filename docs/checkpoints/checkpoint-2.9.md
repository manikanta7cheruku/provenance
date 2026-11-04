# Checkpoint 2.9: The opportunities workbench

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.9-workbench`. Decision: [ADR-0041](../adr/0041-workbench-decisions-and-server-side-list.md). Runbook: [workbench decisions](../operations/runbooks/workbench-decisions.md). Builds on the job posting flow ([1.8](checkpoint-1.8.md)), the evidence check ([1.9](checkpoint-1.9.md)), duplicate detection ([2.7](checkpoint-2.7.md)) and imports ([2.8](checkpoint-2.8.md)).

## What this checkpoint is for
Finding and reading jobs is only half the work. The other half is choosing: which to keep, which to drop, which to prepare for, and where you applied. This checkpoint turns Opportunities from a list into a workbench for that, with filters, views, keyboard use, bulk actions and a record of what you applied for, and it does so without ever hiding that you can undo your choices and that the product never applies for you.

## 1. Build

**Decisions.** Save, dismiss, approve for preparation, mark applied, and the reversals (unsave, undo dismiss, undo applied), plus archive. The server decides which are on offer and the screens show exactly those. A job a hard requirement rules out cannot be approved for preparation. Marking applied names the company and role, asks the day and can be undone. Every move is logged without any note text.

**The list.** Six views with counts (Active, Saved, Applications, Dismissed, Archived, All). Search across title, company, place, source and your notes. Filters for where the work happens, whether you can take it, fit, level, kind of work, source, company and place, with counts. Sorting by date added, title, company, fit, eligibility or date applied, in either direction, with jobs that lack a value last. The list and every filter live in the address.

**Saved views.** Name a view and its filters, apply it later, delete it. Up to 20, names unique without regard to case.

**Bulk.** Check several jobs and act on them together. Each job reports done or why not. Undo works for the whole move.

**Keyboard.** J and K or the arrow keys move, Enter opens, S, D, P, A act, X selects, / searches, ? lists the shortcuts. Off while typing and while a window is open. Every shortcut has a visible button.

**Detail pane and notes.** At wide widths a pane beside the list shows the selected job, its decision actions and a private note. Below that, the job page opens instead. The job page has the same decision bar and note.

**Add from Find jobs.** An "Add to my jobs" button on each found job makes a private posting that can be read, saved and tracked. Duplicate detection links it to its public original.

**Data.** Migration 0014: `job_decisions`, `job_decision_events`, `workbench_views` (Row Level Security, forced) and `source_job` as an acquisition method. Routes: `GET /workbench`, `POST /workbench/bulk`, `GET|POST /workbench/views`, `DELETE /workbench/views/{id}`, `POST /jobs/{id}/decision`, `PUT /jobs/{id}/note`, `POST /search/jobs/{id}/add`. The job detail carries its decision.

## 2. UX

- Save, dismiss and applied can always be taken back, and the message after an action says so with an Undo button that the keyboard reaches.
- Approve says what it does ("Preparation arrives in a later step") instead of implying more.
- Marking applied says the product never applies for you.
- Every empty view says what is empty, why it matters and what to do next. A search with no matches says so differently from an empty view.
- The fit column says "Not checked yet" instead of showing a made-up value.

## 3. Technical acceptance criteria

1. Every allowed move works and every other move is refused with a sentence. The actions offered are never refused.
2. A hard-rule job cannot be approved, singly or in bulk, and the button is not offered.
3. Undo applied returns the job to where it was. Applying with a future day is refused.
4. Every move is logged without note text. Decisions, notes, views and logs belong to their owner (Row Level Security) and go with the posting.
5. Filters combine as stated (OR within, AND across, no value does not match), sorting keeps missing values last, unknown values are dropped, counts are right.
6. The fit band equals the one on the job page.
7. A bulk move reports each job, never touches another person's job, and is bounded.
8. Saved views are cleaned like requests, private, unique by name and limited.
9. Only a job from a source that may be used right now can be added from Find jobs.
10. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the workbench with its pane, with filters open, with rows selected, with the shortcut list and the apply confirmation open, on an empty view, on Applications and on the job page, in light and dark. Views are buttons with `aria-current`. The selected job is `aria-current` and announced. Checkboxes and buttons name the job. Status is words beside the dot. Shortcuts never replace a visible control and are off in fields.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_pipeline.py` | the state machine and the list rules |
| `tests/integration/test_workbench.py` | the database: decisions, log, notes, list, bulk, views, add from a source |
| `src/features/opportunities/workbench.test.tsx` | the query in the address, the decision bar, notes, the workbench |
| `e2e/workbench.spec.ts` | views, search, filters, sorting, keyboard, apply, pane, bulk, saved views, empty states, narrow layout, Find jobs, axe in both themes |

## 6. Commit

```
feat(workbench): add decisions, filters, views, bulk actions and keyboard flow
```

## 7. Interview defense

- Why the decision lifecycle is a state machine in code and why the interface asks the server what to offer.
- Why Save, Dismiss and Applied are reversible and approve and archive are not, and why there is no "submitted" state.
- Why the list rules are on the server and tested as pure functions, and why a table library was not needed.
- Why "no value" does not match a filter, and why the fit band is computed on read.
- How the keyboard flow stays accessible: visible equivalents, off in fields, announced.
- What was not proven: use by a real person with a real list, a screen reader pass, lists past 500.

## 8. Verified and not verified

Verified: all tests above with the real database; the keyboard flow, bulk, views and empty states in a real browser against a stand-in server.

Not verified: a screen reader pass (3.7), a real person's list (carryover), a salary filter (not offered, carryover), lists past 500 jobs, and the drawer and compact layouts of the UX specification (the job page opens instead).

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0014. Add a few jobs on Opportunities, then try the keys: J and K, S, D, X, ? and /. Mark one applied, open Applications, undo it. Save a view with a filter and apply it again. On Find jobs, add a found job to your jobs.
