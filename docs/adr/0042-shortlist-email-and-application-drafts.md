# ADR-0042: The shortlist email and application drafts

Status: Accepted (checkpoint 2.10).

## Context
After the workbench (2.9) a person can decide about jobs. Two things are still missing for the loop to close. They cannot be reminded of the few jobs worth their time without opening the product, and when they decide to apply they start from a blank page. Both are risky in the product's own terms. An email is a message sent on someone's behalf to an address, on a schedule, with a person's private job data in it, and it must never become noise or a duplicate. An application text written by a model is exactly where a product like this is tempted to invent a number or a skill, and a person who sends it pays for the lie.

## Decision

### The shortlist email

**Opt in, per person, on their own clock.** Off until the person turns it on. Daily or weekly, an hour, their own time zone, and how many jobs (1 to 10). The next time is worked out on their local clock (`pv_domain.shortlist.next_run`), so "Monday 8" stays Monday 8 across a change of clocks. A local time that does not exist (the skipped hour) runs after the gap, and one that happens twice runs the first time. It goes only to a verified address and cannot be turned on for an unverified one.

**Selection is deterministic and explained** (`pv_domain.shortlist.select_shortlist`, no model). A job is a candidate only when it is still open to a decision (new, saved or approved for preparation), its evidence check is complete, no hard requirement rules it out, and its fit is Strong or Good. A job that was in an earlier email is never sent again. Candidates are ranked by fit, then by how clear eligibility is, then saved jobs before new ones, then newest, with ties broken by id so the order never changes. Every job carries its reason, written from facts already computed: the band, how many required requirements are supported (the same scoring sentence the job page shows) and one eligibility sentence. The list and the preview on the settings page come from one function, so what is previewed is what is sent. Only jobs the person has added are considered. Jobs found by polling are not sent unless the person adds them.

**One task per due time that arranges the next** (`send_shortlist`, like polling a source). Saving the settings works out the next time and queues it. The task re-reads the settings, so one for a time that is no longer the next one (turned off, schedule changed) does nothing and queues nothing. A run row is unique per person and time, so a retried task cannot record or send a time twice. Mail trouble that may pass is retried, and on the last attempt the run is recorded as failed and the next time is **still queued**, so one bad day does not end the email. The next time is worked from now (or the due time if later), so a worker that was down does not send a pile of old emails. Nothing worth sending is a recorded "nothing", not an empty email. An address that is not verified when the time comes is a recorded "skipped".

**What the email is.** Plain text. No images, no tracking, and links only into the product (never to an employer). It says why the person got it, lists each job with its reason, says the product does not apply for anyone, and says when the next one comes and how to change or stop it. The address is read from the account when the task runs and is never put in a task payload. "Send me one now" queues a manual send (limited to 5 a day) and arranges nothing further.

**Delivery is at least once.** If the worker dies after the mail server accepted the message but before the run was recorded, the retry sends a duplicate. A duplicate shortlist is harmless and is preferred over a lost one.

### Application drafts

**The model writes, code checks every claim, the person owns the text.** A draft is a cover note (one per job) or an answer to a question (common questions, or the person's own), at most 8 per job. `pv_llm.draft` asks for the wording, naming everything by labels code assigned (R1, E1) between markers the text cannot contain, and tells the model that nothing inside them is an instruction.

**Grounded by construction.** A draft is made only for a job whose evidence check is complete, and only from the evidence that check found for requirements the person meets or partly meets. A job with nothing supported has nothing true to write from, and that is a visible result (and the model is never asked). Requirements with no support are named to the model only so it does not claim them. The prompt forbids adding a number, name, tool, employer, date, salary or visa detail that is not in the evidence, and forbids a greeting, a sign-off or placeholders.

**Every claim is checked, with the same checker as resume tailoring** (`pv_domain.drafts.verify_draft` over `pv_domain.tailoring.verify_text`). Numbers, names and tools, and words the job asked for must be in the evidence or in the job's own heading (title, company, place). The words of a letter ("Dear", "Hiring", "Thank you") are not claims. The claims that are in neither are stored with the draft and shown to the person by name and kind. **They are shown, never hidden, and the text is kept as written.** The check runs again on every edit, against the evidence passages kept with the draft, so the person sees at once when they add something unsupported and when they remove it.

**Always a draft.** Every screen that shows one says: Draft. Written by AI from your own evidence. Check every line. Nothing is sent anywhere. The product has no way to send a draft and never applies. Writing a draft again does not throw away the person's edits unless they agree to it. A task for an older request does nothing, and the earlier text stays until the new one is ready.

### Tracker polish
Applications show how long ago each was made, and the pane points to the drafts on the job page. Follow-up reminders and a timeline of stages are carryover.

## Alternatives considered
- **Let the model choose the shortlist.** Rejected: it cannot explain itself, cannot be tested case by case and would make the email unpredictable. A model may write a reason sentence later. It never chooses.
- **A global scheduler that scans for due users.** Rejected: it needs its own bootstrapping and a lock. A task that arranges its own next run already works for polling and survives restarts through the queue.
- **Block a draft that has an unsupported claim.** Rejected for drafts. Resume tailoring blocks because applying would write into the resume. A draft is the person's own text to edit, so the right behaviour is to name the claims and make fixing them easy.
- **Send HTML mail with buttons.** Rejected: plain text cannot render wrongly or carry tracking.
- **Store the address in the task.** Rejected: a payload is stored, retried and shown to administrators. The address is read when the task runs.
- **Draft from the whole resume and profile.** Rejected for now: the evidence the check cited is the part already linked to this job's requirements. Using more is carryover.

## Consequences
- Drafts need a real model, which is not set up. They were proven with a stand-in. The claim check is a heuristic (words and numbers, not meaning), so a paraphrase that changes a fact is not caught. Both are recorded as carryover.
- The shortlist only holds jobs the person has added and checked. A person with no checked job gets no email, and the settings page says why.
- Time zone names come from the browser. A browser may list an older alias, which the server also accepts.
- No one-click unsubscribe: the email links to the settings page, which needs a sign-in (carryover).

## Evidence
Unit tests: cleaning and refusing schedules, next time across daily and weekly schedules, zones, the skipped and repeated hour, a year of times for six zones, selection (filters, ranking, repeats, limits, order independence), the reason sentence, draft claims (supported, number, tool, job word, heading, letter words), question keys, the prompt (labels, markers, injection stays inside, fresh markers, retry, refusal) and the email text (plain, no tracking, links only into the product). Integration tests with the real database: the new tables' security and checks, drafts (blocked until checked, queued, same question one draft, the limit of 8, a good draft with evidence, an invented fact named, bad output and a missing key and provider trouble as visible results, nothing supported means the model is not asked, older and deleted tasks do nothing, editing re-checks, writing again keeps edits unless agreed, privacy, deleting, audit without text), and the shortlist (off by default, verified only, next time and queued task, changing and turning off, preview equals email, dismissed and applied jobs left out, sending with reasons, no repeat on retry or for a sent job, an empty week sends nothing, unverified skipped, stale tasks do nothing, mail trouble recorded and the next time kept, a late worker, send one now, privacy, audit without the address). Browser tests with accessibility checks in both themes for every draft state and the settings.
