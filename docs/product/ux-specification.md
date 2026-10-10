# Product UX Specification

Status: Decided (Phase 0 amendment). Together with [design-system.md](../architecture/design-system.md) and [ai-ux-patterns.md](ai-ux-patterns.md) this forms the **Product UX + Design System Specification**.

UX is a first-class workstream. A checkpoint is not complete when the backend works. It is complete when a user can understand and act on what the backend produced.

## 1. UX principles

1. **Evidence before verdict.** Every conclusion shows what supports it, within one click.
2. **Say what was done, never more.** "Analyzed 18 LinkedIn jobs imported by you."
3. **The user decides.** Every consequential action has a visible approval step that names the object.
4. **State-complete.** Every screen defines loading, empty, partial, error, retrying, permission, quota and offline states before it ships.
5. **Recoverable.** Every failure offers a next step: retry, correct, or a contact route.
6. **Dense but calm.** Work screens favor information density. Onboarding and empty states favor clarity.
7. **One language.** Verdicts, evidence kinds, statuses and actions look and read the same everywhere.
8. **Keyboard and screen reader first-class.** Not an afterthought.

## 2. Product experience goals

| Goal | Measure |
|---|---|
| Time from sign-up to first analyzed job | About six minutes |
| A user can explain why a job was ranked as it was, without developer tools | Usability check at 1.6 |
| A user can tell fact from inference from AI suggestion on every analysis screen | Usability check at 1.6 |
| Zero dead ends: every error and empty state has a next action | Review checklist per checkpoint |

## 3. Information architecture

```
Provenance
  Opportunities          work queue, filters, saved views
    Job detail           overview, eligibility, requirements, evidence, score, risks, action
      Prepare            career preparation (3.2)
      Tailor resume      review of proposed changes (2.6)
  Saved
  Applications           the user's own record of what they applied to
  Profile                entries, evidence, connectors, preferences
  Runs                   run history, then Run Inspector (3.5)
  Settings               account, usage and plan (3.3), data export and deletion, system status
  Admin (role gated)     health, sources, queues, usage, security events (3.5)
```

Imports (URL, paste, CSV, XLSX) start from Opportunities ("Add jobs") and are not a separate top-level area.

## 4. Navigation structure

- Primary: Opportunities, Saved, Applications, Profile, Runs, Settings.
- 900px and up: fixed left sidebar, content area scrolls, persistent detail pane inside Opportunities.
- Below 900px: header with a Menu button, collapsible primary navigation, detail opens as its own screen.
- URL structure: `/opportunities`, `/opportunities/:jobId`, `/saved`, `/applications`, `/profile`, `/runs`, `/runs/:runId`, `/settings`, `/admin/...`. Every meaningful state is addressable by URL.
- Authentication screens live outside the shell: `/signin`, `/signup`, `/verify-email`, `/reset-password`.

## 5. Primary user journeys

The end-to-end flow is in [user-journey.md](user-journey.md). Each journey is checked at the checkpoint that completes it:

| Journey | Completed at |
|---|---|
| Sign up, sign in, recover access | 1.2 and 1.3 |
| Upload resume, correct profile | 1.5 |
| Paste a job, understand the analysis | 1.6 |
| Discover or import jobs, rank, decide | 2.1 to 2.5 |
| Tailor resume with review | 2.6 |
| Connect GitHub, enrich evidence | 3.1 |
| Prepare for interviews | 3.2 |

## 6. Screen and route inventory

| Route | Screen | Checkpoint | Notes |
|---|---|---|---|
| any | App shell, navigation, status indicator | 1.1 | Built |
| `/settings` | Settings (the `settings` feature): account, password, system status | 1.1 and 1.2 | Built |
| `/signin` `/signup` | Authentication (the `auth` feature) | 1.2 | Built |
| `/forgot-password` `/reset-password` `/verify-email` | Recovery flows | 1.3 | Built. Verification is enforced only when EMAIL_VERIFICATION_REQUIRED is true |
| `/runs` | Minimal run list | 1.4 | Full inspector 3.5 |
| `/profile` | Resume upload, parse status, editable profile, evidence | 1.5 | |
| `/opportunities` | Basic list and paste-a-job | 1.6 | Full workbench at 2.5 |
| `/opportunities/:id` | Job detail and analysis | 1.6 | Core trust screen |
| `/opportunities` (add jobs) | Import flow | 2.4 | |
| `/saved` `/applications` | Lists and tracking | 2.5 | |
| `/opportunities/:id/tailor` | Tailoring review | 2.6 | |
| `/settings/connections` | GitHub connection | 3.1 | |
| `/opportunities/:id/prepare` | Career preparation | 3.2 | |
| `/settings/usage` | Plan and usage | 3.3 | |
| `/admin/*` `/runs/:id` | Admin and Run Inspector | 3.5 | |

## 7. Low-fidelity wireframes

### 7.1 Opportunities workbench (desktop)

```
+-----------+---------------------------------------------------------------+
| Provenance| [Search jobs      ] [Filters v] [Saved views v]     [Add jobs]  |
|           +--------------------------------------+------------------------+
| Opportu-  | Company    Role         Fit    Elig.  | Acme AI                |
| nities    | > Acme AI  AI Engineer  Strong Yes    | AI Engineer            |
| Saved     |   Nova     ML Engineer  Good   Unsure | Strong match           |
| Applica-  |   TechCo   GenAI Eng.   Review Yes    | 9 of 11 required       |
| tions     |   ...                                 | requirements supported |
| Profile   |                                       |                        |
| Runs      | 41 found, 12 strong, 18 possible,     | [Open] [Save] [Prepare]|
| Settings  | 11 ineligible                         |                        |
| System ok +--------------------------------------+------------------------+
+-----------+---------------------------------------------------------------+
```

### 7.2 Job detail (trust center)

```
Acme AI  |  AI Engineer                         [Save] [Dismiss] [Prepare]
Hyderabad or remote | Company careers | Posted 3 days ago | INR 8 to 12 LPA
Strong match: 9 of 11 required requirements supported
Eligibility: Eligible. No hard blockers found.          Open original posting

Overview | Eligibility | Requirements | Evidence | Score | Risks and gaps

Requirements
  Requirement                  Verdict        Evidence kind   Confidence
  Production Python            Met            Direct          High       >
  Kubernetes in production     Not verified   Missing         -          >
  2+ years experience          Partial        Inferred        Medium     >

 (expanded row)
  From the posting:    "2+ years of backend experience"
  From your evidence:  Internship at X, 14 months  [Project Y entry]
  Why Partial:         14 months is below 24 months. The gap is real.
  What you can do:     add other relevant experience  |  This is wrong
```

### 7.3 Import flow

```
1 Choose how          2 Preview and validate           3 Confirm
URL | Paste | CSV     18 rows: 15 ready, 2 duplicate, 1 invalid (missing title)
                      [row table with per-row reasons]  [Fix] [Skip] [Import 15]
```

### 7.4 Tailoring review

```
Original bullet        | Proposed bullet                    | Support
Built backend APIs     | Built 30+ FastAPI endpoints ...    | Supported: Project X
                       | [Edit] [Accept] [Reject]           | 1 claim not supported
```

### 7.5 Mobile job detail

```
< Back                      Save  Dismiss
Acme AI
AI Engineer
Strong match
9 of 11 required supported
Eligible
[Requirements] [Evidence] [Score]
 (stacked verdict rows, tap to expand)
```

## 7A. Interaction patterns

| Pattern | Rule |
|---|---|
| Selection | One selected row at a time. Selection is shown by the selected role plus a leading accent bar, and is also exposed to assistive technology |
| Progressive disclosure | Summary first. Expanding a row reveals reasoning, then evidence, then provenance. Expanded state is keyboard operable and remembered while the page is open |
| Detail | Wide: persistent pane beside the list. Medium: drawer. Compact: separate screen. Back always returns to the same list position |
| Inline editing | Edit in place with explicit Save and Cancel. Escape cancels. A changed value is marked as edited by the user |
| Forms | Labels above fields. Validate on blur and on submit, never on every keystroke. Errors sit beside the field, are linked with aria-describedby, and the first error receives focus on submit |
| Confirmation | Only for destructive or consequential actions. Names the object. Reversible actions use undo instead |
| Undo | A toast with Undo for reversible actions (unsave, undo dismiss). It persists long enough to read and is reachable by keyboard |
| Feedback timing | Under 100ms: no indicator. Longer: a named loading state. Long operations become background tasks with persisted progress |
| Navigation | Every meaningful state has a URL. Focus moves to the page heading after navigation. Browser back behaves predictably |
| Keyboard | Visible equivalent for every shortcut. Escape closes the topmost overlay and returns focus to its trigger |
| Motion | Only to show a state change, using the shared durations. Reduced motion respected |

## 8. High-fidelity designs for critical screens

Status: **not yet produced.** Phase 0 defines these screens in complete detail (sections 7 and 9 here, plus ai-ux-patterns.md) but contains no visual mockups. Interactive visual prototypes of the two critical screens (Opportunities workbench and Job detail) are the first task of checkpoint 1.5, produced from the real tokens before components are built, and reviewed before checkpoint 1.6 starts. The gap is recorded here deliberately.

## 9. State catalog

Every screen that shows data defines each applicable state.

| State | Rule |
|---|---|
| Loading | Skeleton or named step ("Fetching posting"). Never an unlabeled spinner. Progress only from persisted counters |
| Empty | What is empty, why it matters, what to do next |
| Partial | Show what exists, label what is pending ("12 of 38 analyzed") |
| Processing | Named step and persisted counts. Leaving the page does not cancel work |
| Error | What happened, is my data safe, will it retry, what can I do. Request id available |
| Retrying | Says it is retrying and when. Shows attempt count |
| Retry available | Visible Retry button. Explains what retry will do |
| Permanently failed | Says why, what is preserved, and the alternative path |
| Permission denied | Plain statement. For inaccessible resources the app shows "not found" |
| Quota exhausted | What limit, how much used, when it resets, what the user can still do |
| Offline or API unreachable | Says data is safe, offers Check again |
| Waiting for you | Names the exact question, offers the answer controls |
| Stale | States when the data was last refreshed and offers refresh |
| Destructive action | Names the object and the consequence, states what is kept, requires a confirming action (not Enter alone), offers cancel as the default focus. Reversible actions use undo instead of a dialog |
| Success | A short confirmation naming what changed. It does not steal focus and is announced politely |

## 10. Operation state models (frontend and backend)

The backend defines the states ([data-model.md](../architecture/data-model.md) section 8) and the frontend renders them. The frontend never invents a state. Where the UI shows something richer than a stored state, it is derived from stored data and listed here.

### 10.1 Background tasks (queue, imports, exports, generation)

| Task state | UI state | Copy pattern | Actions |
|---|---|---|---|
| queued | Queued | "Waiting to start" | Cancel |
| running | Processing | Current step and persisted counts | Cancel |
| retry_scheduled | Retrying | "Retrying (attempt 2 of 5) at 14:32" | Cancel |
| succeeded | Completed | Result summary | Open result |
| dead_letter, user-initiated operation | Retry available | What failed and what is preserved | Retry (creates a new task) |
| dead_letter, system operation | Permanently failed | Why, what to do instead | Details |
| cancelled | Cancelled | What was kept | Run again |

### 10.2 Analysis of a job (match state)

| Match state | UI state | Notes |
|---|---|---|
| queued | Queued | |
| analyzing, no verdicts persisted | Processing | Shows the current step and counts |
| analyzing, at least one verdict persisted | Partial result | "6 of 11 requirements checked". Verdicts shown as they land |
| needs_user_input | Waiting for you | The exact question and answer controls |
| analysis_failed | Failed, then Retry | Retry transitions analysis_failed to queued |
| gate_failed | Not eligible | Shows the failed gate, not a score |
| scored and later | Completed | |

### 10.3 Resume upload

| Where | State | Source |
|---|---|---|
| Browser only | Idle | Nothing chosen |
| Browser only | Uploading | Bytes in flight. A transport failure shows Failed with Retry and stores nothing |
| Server | Uploaded | parse_status uploaded |
| Server | Parsing | parse_status parsing |
| Server | Parsed | parse_status parsed, flagged_field_count 0, review pending |
| Server | Needs correction | parse_status parsed, flagged_field_count above 0, review pending |
| Server | Confirmed | review_status confirmed |
| Server | Failed, then Retry | parse_status parse_failed. Retry creates a new parse task |

This sequence (Idle, Uploading, Uploaded, Parsing, Parsed, Needs correction, Failed, Retry) is the contract for checkpoint 1.5.

### 10.4 Rule

If a screen needs a state that is not stored or derivable from stored data, the backend model is extended first through the data model and an ADR. The screen does not add it locally.

## 11. Responsive behavior

| Width | Behavior |
|---|---|
| 900px and up (Wide) | Sidebar plus content. Opportunities uses a split pane with persistent detail |
| 600 to 899px (Medium) | Single column. Menu in header. Detail opens as a drawer |
| Below 600px (Compact) | Single column. Tables become structured rows. Detail is its own screen. Touch targets at least 44px where density allows |

Content never requires horizontal page scroll. Wide tables scroll inside their own container.

## 12. Accessibility requirements

Target WCAG 2.2 AA where practical.

- Landmarks: header, nav, main. Skip link first in tab order.
- One h1 per page. Focus moves to it on in-app navigation.
- Document title changes per route.
- Visible focus on every interactive element.
- Color is never the only signal.
- Forms: labels, descriptions, error messages associated and announced.
- Dialogs: focus trap, Escape closes, focus returns.
- Status changes use polite live regions.
- Reduced motion respected.
- Contrast: 4.5:1 for text, 3:1 for interface components. Token pairs are checked (see checkpoint-1.1.md for the 1.1 results).
- Automated checks (axe) arrive in CI at 1.5. Manual keyboard and screen reader pass on key flows at 3.6.

## 13. Keyboard navigation

The shortcut map is in [design-system.md](../architecture/design-system.md) section 6. Shortcuts never replace visible controls, are disabled inside text fields, and are discoverable with `?`.

## 14. Content and UX writing conventions

- Plain and specific. Sentence case. No em dashes.
- Say what the system did: "Analyzed", "Imported by you", "Found".
- Predictions are hedged: "Likely", "Potential", "High-priority preparation area".
- Never "AI-powered" as a headline.
- Errors name the cause in user terms and the next step.
- Numbers come from stored data and are rounded deliberately.
- Buttons are verbs: "Save", "Prepare materials", "Mark as applied".
- Consequential actions name the object: "Mark Acme AI, AI Engineer as applied".

## 15. Components and states

The component list and state matrix are in [design-system.md](../architecture/design-system.md). A component is done only when every state exists in the component gallery in both themes.

## 16. Per-checkpoint UX gate

Every checkpoint carries technical, UX and accessibility acceptance criteria (see the implementation plan). A reviewer must be able to complete the checkpoint's user task using only the UI.
