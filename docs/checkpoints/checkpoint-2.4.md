# Checkpoint 2.4: Resume tailoring with a grounding check

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.4-resume-tailoring`. Decision: [ADR-0036](../adr/0036-resume-tailoring-and-grounding.md). Runbook: [suggestions fail or look wrong](../operations/runbooks/resume-tailoring-failed.md). Builds on the evidence check of [checkpoint 1.9](checkpoint-1.9.md) and the studio of [2.1](checkpoint-2.1.md) to [2.3](checkpoint-2.3.md).

A student tailors a resume to a job by moving the job's words into it. This checkpoint makes that faster and keeps it honest: a model proposes better wording for the bullets and summary of a resume, code checks that the new wording adds no fact the person cannot back up, and the person accepts, edits or rejects each change.

## 1. Build

**The flow.** In the studio, "Tailor to a job". Pick a job whose evidence check is finished (the job page now links here), press Suggest changes, review, decide.

**What can change.** Bullet lists and the summary paragraph, in guided and free canvas resumes. Names, headings, dates, contacts and employers are never offered to the model.

**What the model sees.** The requirements the evidence check confirmed (met or partial), the evidence it cited, and the parts of the resume that can change, each by a label that code assigned (R1, P1, E1). Requirements nothing confirms are listed as "do not claim".

**The grounding check (`pv_domain.tailoring`).** Every number, name or tool (a capitalised word mid-sentence, an acronym, a word with digits or symbols) and every word the job asks for in the new wording must appear in the old wording of that part or in the evidence the suggestion cites. Numbers match as whole numbers. A suggestion that fails is stored as blocked with each claim and where it was or was not found.

**Review screen.** Each suggestion shows the old and new wording side by side with changed words underlined or struck through, the reason, the requirements it helps with, the evidence it uses, and a plain line: "Every fact checked" or "Not found in your resume or evidence: looker, 60". Buttons: Accept, Edit, Reject. A blocked suggestion cannot be accepted and says why. Below the list, "Not added to your resume" shows what the job asks for that nothing confirms.

**Accept.** Re-runs the check against the evidence as it is now, then changes only that part, as a normal save with the resume's revision as a lock and a restore point. If that part changed since the suggestion, nothing is changed and the person is told to ask again. **Edit** re-checks the person's own wording. **Reject** changes nothing.

**Server.** `resume_tailorings` and `tailoring_suggestions` (migration 0009, Row Level Security), a `tailor_resume` task in the worker with the same durable pattern as the evidence check (a task for an older start does nothing, retry with backoff, a visible failure with no key), routes under `/studio`, rate limits, audit records, and usage recorded in the ledger.

## 2. UX

- Nothing changes in the resume until the person accepts it.
- Every suggestion says why it exists, what it relies on, and what was checked.
- A blocked suggestion explains itself and offers a way forward (edit it, reject it, add the detail to the profile).
- Honest empty states: no checked job, no suggestions, nothing confirmed.
- Changes are marked by underline and strike as well as weight, never color alone.

## 3. Technical acceptance criteria

1. Only bullet lists and summary paragraphs are units. Applying a change replaces that part only and leaves everything else, including the original document object, untouched.
2. A suggestion with an invented number, tool, employer or job keyword is blocked. The same input always gives the same result. Numbers are matched whole.
3. Labels the model made up (parts, requirements, evidence) are dropped, a part is suggested once, and a no-op suggestion is not shown.
4. A blocked suggestion cannot be accepted, including when the stored result is changed in the database (accept re-checks).
5. An edit is re-checked and cannot add a fact. An empty or oversized edit is refused next to the field.
6. Accept uses the revision lock, keeps a restore point, refuses a part that changed since, and cannot be repeated.
7. A missing key, a provider outage and a deleted or restarted run are visible and leave the resume unchanged.
8. Nobody else can see, start or decide on someone's tailoring, and their evidence never appears in another person's prompt.
9. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the review screen with the evidence and "not added" lists open and with the edit box open, in light and dark. Buttons carry the part they act on in their names ("Accept change, Data Intern, Kestrel Analytics") and start with their visible text. A disabled Accept is described by the reason. Progress and results are announced.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_tailoring_check.py` | units, applying, claims, the check, cleaning |
| `tests/integration/test_tailoring.py` | the API, worker, database and a stand-in model: 21 cases |
| `tests/unit/test_worker_handlers.py` | the task is registered |
| `src/features/studio/tailor/diff.test.ts` | the word difference and line pairing |
| `e2e/tailoring.spec.ts` | start, review, blocked, accept, reject, edit, empty states, axe in both themes |

## 6. Commit

```
feat(studio): add resume tailoring with a grounding check
```

## 7. Interview defense

- Why a model proposes and code verifies, and why a second model as judge is not enough.
- What counts as a claim, what is free, and what the check cannot see (a lowercase tool that the job never names, and misleading emphasis made of true words).
- Why only confirmed requirements and cited evidence are offered, and why labels are assigned by code.
- Why accept re-checks, why edits are checked, and how the revision lock and the part check protect the resume.
- How a task for an older start does nothing and how failures leave the resume untouched.

## 8. Verified and not verified

Verified: tests above (unit 657, integration 316, PDF 60, web 240, Playwright 147), with the real database, queue handler, API and a stand-in model; the review screen in a real browser with accessibility checks.

Not verified: a real model. Everything above uses a stand-in, so how often a real model proposes useful changes, how often it triggers a block, and how it handles real resumes is not measured. A person using the review screen. The check against a larger set of real resumes and jobs (the roadmap calls for an evaluation set of unsupported claims, which is not built yet). A tailoring run in a free canvas resume with many text boxes in a real browser. A screen reader session by a person.

Limits you should know: a suggestion rewrites its lines as plain text, so bold or links inside those lines are not kept. Lowercase tools that the job does not name are not detected as claims. The check is conservative for facts and generous for ordinary words.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This needs a Gemini key in `.env` for real suggestions (`.\scripts\pv.ps1 ai-check`). Paste a job in Opportunities, press Check my evidence, then open Resume studio and use "Tailor to a job". Without a key you should see "The suggestion service is not set up yet".
