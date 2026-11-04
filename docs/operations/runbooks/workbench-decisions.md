# Runbook: Workbench decisions and lists

A job is in the wrong state, an action is missing or refused, a bulk move skipped jobs, a saved view will not apply, or the list is slow or cut off.

## Detection
- The job page ("Your decision") and the workbench show the state and the actions on offer.
- `audit_events` actions `job.decision` (the action only) and `job.decision_bulk` (the action and a count). Never a note.
- `job_decision_events` shows every move of a job in order, with the states either side.

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| "Approve for preparation" is missing | A hard requirement rules the job out (eligibility not eligible) | Expected. Change the profile answer that caused it, or save or dismiss the job |
| "Save is not available for a job that is ..." (409) | The job moved since the page loaded (another tab, or a bulk move) | Reload. The actions shown always come from the server |
| Undo applied returned a job to New | The log had no usable earlier state | Expected for old data. The person can save or approve it again |
| A bulk move says "could not be changed" for some jobs | Those jobs are not in a state that allows the action | Read the reason per job in the answer. Nothing was changed for them |
| "Only the newest 500 jobs are shown" | The cap | Filter, or archive older jobs |
| Fit shows "Not checked yet" | The evidence check has not been run or is not complete | Open the job and run the check |
| A saved view applies fewer filters than were set | Unknown values are dropped when a view is saved | Expected. Recreate the view |
| "Add to my jobs" says 404 | The job's source is not usable now (switched off, review out of date) or the job closed | See the [source health runbook](source-health.md) |
| The list is slow | Many jobs with analyses | Check the database; the band is three queries for the whole list. Archive old jobs |

## Mitigation
Decisions are the person's own records and independent of reading and scoring. If the workbench misbehaves, the job page and the old list endpoints (`GET /jobs`) still work.

## Recovery
A wrong state can be corrected with the reverse actions. As an administrator, `job_decisions` can be corrected in SQL with a matching row in `job_decision_events` so that Undo applied still works. Never delete events for a job that is currently applied.

## Prevention
Every new state or action gets a row in the transition tests, including the refused combinations. Keep "what is offered" and "what is allowed" in one function.
