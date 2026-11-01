# Runbook: Sources, the registry and search planning

A person sees a source marked unavailable that should work, a plan that searches nothing, a company that will not resolve, or "searching by sentence is not set up". An administrator needs to change a source safely.

## Detection
- The Find jobs page (the list of sources and each plan).
- `GET /api/v1/admin/sources`: every record, whether its review expired, and `enable_blocker`, the reason it cannot be enabled.
- `llm_calls` with purpose `search_intent` and a non-ok status (no text is stored).
- Audit events `source.updated` (fields changed, never text).

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| Every source is Import needed or Unavailable | No adapter exists yet (checkpoint 2.6) and nothing is enabled. This is the expected state today | Nothing to fix |
| A source says "It is switched off" | `enabled` is false | Check `enable_blocker`. If null, enable it. If not, the blocker says what is missing |
| "Its terms have not been verified yet" | `compliance_status` is unverified | Read the terms yourself, then record the review (below) |
| "The review of its terms has expired" | `terms_checked_at` is older than `SOURCE_REVIEW_WINDOW_DAYS` | Read the terms again and set a new date |
| "It does not cover X" | The source lists a coverage that does not include the place asked for | Expected. Edit `geographic_coverage` only if the source does cover it |
| A company is "Not in our list" | It is not in `companies` | Add it to `registry_data/companies.json` and restart the API, or tell the person to import its jobs |
| A company asks "Which one did you mean" | Two or more names are close | Expected. The person chooses. If one name should always win, add an alias |
| Searching by sentence says the AI service is not set up | No `GEMINI_API_KEY` on the API | Set the key, restart the API. Planning by fields still works |
| Searching by sentence says the AI service did not answer | The provider failed or answered twice with something unusable | Try again. Check the provider and `llm_calls` |

## Recording a review (administrator)
1. Read the source's current official terms and documentation. Do not rely on this repository's notes.
2. `PATCH /api/v1/admin/sources/{key}` with `compliance_status`, `terms_checked_at` (today), `terms_url` and `verification_owner` (your name and what you read), and update `compliance_notes`.
3. Only then set `enabled` to true. The API and the database both refuse if anything is missing.
4. An adapter must exist before the source can be searched. Enabling without one leaves it at "Import needed".

## Mitigation
Switch a source off at once with `enabled: false` if its terms change or it misbehaves. That takes effect on the next plan.

## Recovery
The registry is seeded from `registry_data/`. A row an administrator edited is never overwritten by the seed. To go back to the seed for one source, clear its `edited_at` in the database and restart the API.

## Prevention
Review each enabled source before its window ends (180 days). Do not add a source without a record of where its terms were read.
