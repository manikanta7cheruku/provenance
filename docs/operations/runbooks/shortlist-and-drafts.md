# Runbook: The shortlist email and application drafts

A person did not get their shortlist email, got one twice, got one with nothing useful, a draft is stuck or failed, or a draft flags claims that look fine.

## Detection
- Settings, Shortlist email: the next time, the history of runs (sent, nothing to send, not sent, could not be sent).
- `shortlist_runs` (one row per due time), `shortlist_items` (the jobs in each email), `shortlist_settings.next_run_at`, and tasks of type `send_shortlist` and `draft_application`.
- `audit_events` actions `shortlist.settings_changed`, `shortlist.send_requested` and `application_draft.started|edited|deleted`. Never the address, a job or a draft text.

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| No email arrived and the history says "Nothing to send" | No job is worth a look that was not sent before | Expected. The preview says what a job needs |
| History says "Not sent: your email address is not verified" | The address was not verified at the time | The person verifies it. The schedule continues |
| History says "Could not be sent" | The mail server refused or was down on every attempt | See the mail runbook for the worker log. The next time is still scheduled |
| Next time is empty while the email is on | The task that arranges the next time died (dead-lettered) | Save the settings again: it works out the next time and queues it. Find why in the [dead letter runbook](dead-letter-task.md) |
| The same email twice | The worker died after the server accepted the message and before the run was recorded | Expected, rare. Not a defect (at-least-once delivery) |
| An email arrived at the wrong hour | The time zone on the settings is not the person's | They change it. The time is on that zone's clock |
| The same job appears in a later email | It cannot, by rule. Check `shortlist_items` for that job and person | If it is a different posting of the same job, the person has two postings |
| Draft says "Check this job against your evidence first" | The evidence check of the job is not finished | Run the check from the job page |
| Draft says "nothing true to write from" | No requirement of the job is supported by the person's evidence | Add evidence to the profile and check the job again |
| Draft says the writing service is not set up | No model key | See [real AI model setup](../../carryover/real-ai-model-setup.md) |
| A draft flags a name or a number that is in the person's resume | The claim check only sees the evidence cited for this job and the job heading | The person adds the evidence to the profile and checks again, or edits the text. If many honest drafts are flagged, record cases for C-84 |
| A draft stays "working" | The task is waiting or retrying | See the [stuck task runbook](stuck-task.md). Writing it again makes a new task and drops the old |

## Mitigation
Both features are independent of the rest. A person can turn the email off at any time (it cancels what is waiting). To stop all shortlist sending, remove `send_shortlist` from the worker registry. Drafts can be stopped by removing `draft_application`. Nothing else is affected.

## Recovery
A person's schedule can always be rebuilt by saving their settings again. A failed draft can be written again. Never edit `shortlist_items` by hand: removing a row makes that job eligible to be sent again.

## Prevention
A new rule for who is in the email gets a test for every combination it touches, and a test that the preview and the email agree. A new kind of claim gets a case in `test_draft_rules.py` before the checker changes.
