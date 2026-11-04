# ADR-0041: The workbench: a decision state machine, a server-side list, and saved views

Status: Accepted (checkpoint 2.9).

## Context
A person can now bring jobs in four ways (1.8, 2.8) and see what each asks for and whether they can take it (1.8, 1.9). What is missing is the work of choosing: which jobs to keep, which to drop, which to prepare for, and which they applied to. Without it the Opportunities page is a list with nothing to do. The workbench is where decisions are made, so it has three risks: a decision that cannot be taken back loses information, an action offered when it should not be misleads (approving a job a hard rule rules out), and a screen that cannot be used by keyboard or screen reader excludes people.

## Decision

**A decision state machine in code** (`pv_domain.pipeline`, pure). This is the person's half of the match lifecycle of [ADR-0014](0014-split-state-machines.md). Six states: New (no row), Saved, Dismissed, Approved for preparation, Applied, Archived. Eight actions: save, unsave, dismiss, undo dismiss, approve, mark applied, undo applied, archive. Every move is checked in `transition()`, and the same function says which actions are on offer (`available_actions`), so the interface can never offer a move the server would refuse (a test checks this for every state).
- **Save, Dismiss and Applied are reversible** (unsave, undo dismiss, undo applied). Approve and archive are not. Undo applied returns the job to where it was before (from the log), not to a fixed state.
- **A job a hard rule rules out cannot be approved for preparation.** It can still be saved, dismissed or marked applied, because those are the person's own records.
- **There is no submitted state.** `applied` is the person's record that they applied on the employer's site. Marking it names the company and role, asks the day (never in the future) and can be undone.
- The reading and scoring states stay with the posting (`ui_state`, the evidence check). The states after approval (materials made, ready to apply) arrive with preparation in Phase 3. Approving today records intent and says so.

**Stored as a decision per posting plus a log** (`job_decisions`, `job_decision_events`, migration 0014, Row Level Security). A posting with no row is New. Every move is logged with the action and the states either side and **no note text**. The log is what Undo applied reads and is the audit trail of the person's own decisions. The private note on a job (up to 2,000 characters) lives on the decision and survives every move.

**The list is built on the server** (`GET /workbench`). Views (Active, Saved, Applications, Dismissed, Archived, All), text search (every word, in title, company, place, source and the person's note), filters (work mode, eligibility, fit, level, kind of work, source, company, place) and sorting are pure functions over rows (`pipeline.select`) and are tested as such. Within a filter any value matches, across filters all must, and a job with no value for a filtered field does not match it, rather than being treated as a match. Missing values sort last in either direction. Unknown values in a request are dropped, not guessed at. Facet counts show what each filter would add. The fit band is computed in three queries for the whole list with the same scoring function the job page uses, so the two can never disagree. The list is capped at 500 jobs and says so.
- **Why on the server and not in a table library.** The product's rule is that the backend decides and the frontend renders. Server-side rules are testable without a browser, shared by the job page and the list, and the page stays a plain semantic table. The roadmap named TanStack Table; it is not used, because a native table with server-side rules does everything this checkpoint needs with less code and a smaller accessibility surface. Recorded as carryover if very large lists ever need virtual rows.

**Saved views** (`workbench_views`) store a name and a query that goes through the same cleaning as a request, so a stored view can never hold anything the list would not accept. Names are unique without regard to case, and a person may keep 20. The current list lives in the address (every meaningful state has a URL), so back, reload and sharing a link work.

**Bulk actions** (`POST /workbench/bulk`, up to 100 jobs) do what they can and report each job: done, or why not. The server offers only actions every selected job has. Mark applied is one job at a time because it asks for a day. The bulk response carries the action that takes the move back, so Undo works for many jobs the same way as for one.

**Keyboard and screen reader.** J and K (or the arrow keys on the list) move the current job, Enter opens it, S, D, P and A act on it, X selects it, / searches, ? lists every shortcut. Each has a visible control. Shortcuts are off while typing, while a window is open and with modifier keys. The current job is announced in a polite region. An action shows a message with Undo that stays 12 seconds and is plain buttons. At wide widths a detail pane sits beside the list; below that Enter and a click on the title open the job page.

**Adding a job found on a source** (`POST /search/jobs/{id}/add`). A result on Find jobs becomes a private posting (`acquisition_method = source_job`) that can be read, saved and tracked like any other. Only a job whose source may be used right now can be added. Duplicate detection (2.7) matches the copy to its public original on read.

## Alternatives considered
- **One state machine for the whole lifecycle in this checkpoint.** Rejected: the later states need preparation, which is Phase 3. The decision half stands alone and the vocabulary leaves room.
- **Filter and sort in the browser.** Rejected for the reasons above, and because the fit band and eligibility are computed on the server.
- **Store the band.** Rejected: it would go stale when the profile changes. It is computed on read, as on the job page.
- **A single "undo" that restores the previous state of anything.** Rejected: it would make approve and archive silently reversible. The interface offers exactly the reversals the product defined.
- **Delete instead of dismiss.** Rejected: dismissing hides, and can be undone. Delete stays a separate, confirmed action on the job page.

## Consequences
- The fit column shows "Not checked yet" for a job whose evidence check has not run. A salary filter is not offered because the reader does not extract salary yet (carryover).
- Every list request loads the person's jobs (up to 500) and computes eligibility for each read job. That is fine at the scale of one person's jobs and is recorded as carryover for larger lists.
- Approving a job has no effect beyond its state until preparation exists.
- A dismiss reason is the private note, not a separate field.

## Evidence
Unit tests: every allowed move, every refused move (the other 34 of the 48 combinations of state and action), undo applied from each past state, the hard-rule block, what is offered in each state and that it is never refused, every view, text search, filters, sorting with missing values, facet counts, and cleaning of untrusted queries. Integration tests with the real database: the forced security and checks on the new tables, each decision, the log without note text, privacy between people, notes, the list with every filter and sort, the fit band equal to the job page's, the 500 cap, bulk (partial success, other people's jobs, limits, the hard-rule skip), saved views (cleaning, privacy, unique names, the limit), and adding a job from a source (usable, closed, disabled, too short, one copy each). Component tests and browser tests with accessibility checks in light and dark, including the keyboard flow, the apply confirmation, bulk with undo, saved views, empty states and the narrow layout.
