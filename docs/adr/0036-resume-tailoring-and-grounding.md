# ADR-0036: Resume tailoring with a deterministic grounding check

Status: Accepted (checkpoint 2.4).

## Context
A student who tailors a resume to a job is tempted to copy the job's words into it. A language model makes that easy and invisible: it will happily write "built Tableau dashboards for 60 stakeholders" because the job asks for dashboards. For a product built around evidence ("jobs with receipts"), a tailoring feature that invents facts would break the one promise that matters. The roadmap names the risk: claim-level verification, and why a second model acting as judge is not enough.

## Decision

**The model proposes. Code checks. The person decides.**

1. **What can be changed (units).** Only the bullet lists of items and the summary paragraph. Names, headings, dates, contacts, titles and employers are never offered to the model, so they cannot change. This works the same for guided and free canvas resumes.

2. **What the model may use.** Only the requirements that the earlier evidence check (1.9) confirmed as met or partial, and only the evidence that check cited. Everything else the job asks for is listed to the model as "do not claim" and shown to the person as "not added, nothing in your profile confirms it". Tailoring needs a finished check for that job first.

3. **Labels, not ids.** The model sees parts as P1, P2, requirements as R1, R2 and evidence as E1, E2, assigned by code in this run. It cannot cite something it was not shown or that belongs to another person. Unknown labels are dropped. This is the same rule as the evidence agent.

4. **The grounding check.** A claim is anything a reader takes as a fact about the person: a number, a name or tool (a capitalised word in the middle of a sentence, an acronym, a word with digits or symbols such as C++ or Node.js), and any word the job asks for. Every claim in the new wording must appear in the old wording of that part or in the evidence the suggestion cites. A number must match as a whole number, so 4 is not found in 40. Anything that adds an unsupported claim is stored as **blocked**, with each claim and where it was or was not found. Ordinary words are free, so a suggestion can reorder, tighten and emphasise what is already true.

5. **Why not a model as judge.** A second model asked "is this true?" is another guess about a guess. It can be talked into agreement by the same text, it gives different answers on different days, and it cannot be tested with a fixed list of lies. The check here is plain code over text: the same input gives the same answer, a list of invented numbers, tools and employers can sit in a test, and the failure it targets (job keywords pasted into a resume) is exactly what it detects.

6. **Verified again when it matters.** Accepting re-runs the check against the evidence as it is now. A stored "not blocked" is never trusted. A blocked suggestion cannot be accepted. A person's own edit of a suggestion is held to the same check, so editing is not a way around it. A person can still write anything they like in the resume itself, because that is their document and their responsibility, and the screen says so.

7. **Accepting is safe.** It changes only the part the suggestion was made from: if that part no longer matches the lines the suggestion was based on, nothing changes and the person is told to ask again. It uses the resume's revision as a lock like every save, keeps the earlier wording as a restore point, and runs the normal document validation.

8. **Nothing is silent.** Every suggestion shows the old and new wording side by side with the changed words marked by underline and strike, the reason, the requirements it helps with, the evidence it uses and the result of the check. Nothing is applied until the person accepts.

## Data
Two tables (migration 0009), both with Row Level Security: `resume_tailorings` (one per resume and job, no resume text) and `tailoring_suggestions` (old and new lines, reason, citations, claims, blocked, edited, status). Starting again replaces the suggestions of the earlier run and makes any task for it do nothing.

## Alternatives considered
- **Let the model rewrite the whole resume.** Rejected: it can change names, dates and employers and cannot be verified part by part.
- **Verify with a second model.** Rejected, see above.
- **Verify only numbers.** Rejected: invented tools and employers are as damaging as invented numbers.
- **Auto-apply high-confidence suggestions.** Rejected: the product's rule is that the person approves anything that goes into their resume.
- **Strict word-by-word grounding.** Rejected: it would block honest rewording ("developed" for "built") and make the feature useless.

## Consequences
- The check is conservative for claims (it may block a true fact that is not in the evidence) and generous for ordinary words (it can allow a misleading emphasis made only of already-true words). The first is fixable by adding the fact to the profile and asking again. The second is why a person reviews every change.
- Lowercase tools that the job does not name (for example "pandas" when the job never mentions it) are not detected as claims unless they are capitalised or in the job text. The checkpoint document says so.
- Rewording a list rewrites its lines as plain text, so bold or links inside those lines are not kept.
- Formatting of headings and dates is untouched, which keeps templates intact.

## Evidence
Domain tests for units, claims and the check (including invented numbers, tools, employers, job keywords, whole-number matching and determinism), 21 integration tests through the real API, queue handler, database and a stand-in model (invented facts blocked, forged labels dropped, accept re-verifies, edits re-verified, stale revision, changed part, isolation between people, no key, provider outage), and browser tests for the review screen with accessibility checks in both themes.
