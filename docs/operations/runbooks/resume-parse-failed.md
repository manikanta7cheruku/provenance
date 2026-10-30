# Runbook: Resume parsing fails

A user uploads a resume and the screen says "Could not read it". Parsing runs in the worker as the `parse_resume` task, so most causes are visible without reading the file.

## Detection
- The user sees a plain sentence on the Profile screen. The short code behind it is stored in `resumes.error_code`.
- Admin, System shows no dead letter for these: a visible parse failure is a result, and the task completes. Only repeated transient trouble ends as a retry on the last attempt.
- The run appears in the user's Runs list as "Failed, retry available" or "Failed", with the failing step.

## Diagnosis
Find the code (database owner shell: `.\scripts\pv.ps1 psql`):

```sql
SELECT error_code, count(*) FROM resumes WHERE parse_status = 'parse_failed' GROUP BY 1 ORDER BY 2 DESC;
```

| Code | Meaning | What to do |
|---|---|---|
| `ai_not_configured` | No `GEMINI_API_KEY` or `LLM_MODEL` on the worker | Set them in `.env`, then `.\scripts\pv.ps1 restart worker`. Run `.\scripts\pv.ps1 ai-check`. Ask the user to press "Read it again" |
| `ai_unavailable` | The provider was busy, rate limited or down for every attempt | Check the provider status and `LLM_MIN_INTERVAL_SECONDS`. Users can retry later |
| `ai_bad_output` | The model answered twice with something that did not match the schema | Look at the `llm_calls` rows for the run (no text is stored). If it keeps happening after a model change, review the prompt version in `pv_llm.resume_parse` |
| `file_missing` | The row exists but the stored file is gone | Check the `files` volume is mounted on both the api and the worker. Ask the user to upload again |
| `file_unreadable`, `encrypted`, `no_text`, `too_many_pages`, `too_long`, `unsafe_archive` | A problem with the file | Nothing to fix on our side. The message already tells the user what to change |

Cross-check the run: Admin cannot see tenant data, but you can read counts and step results in `workflow_steps` for the run id (no content is stored there).

## Mitigation
- If one provider fails for everyone, stop users from retrying in a loop: nothing needs doing, the rate limit (10 re-reads per hour per user) already caps it.

## Recovery
- After fixing configuration, ask affected users to press "Read it again". There is no bulk replay on purpose: re-reading replaces entries and costs model calls.
- Files stay in storage until the user deletes them.

## Prevention
- Run `python -m pv_llm.check` after any model or key change.
- Watch the share of `parse_failed` resumes and the average `dropped_entry_count` (the evaluation harness in 3.6 will track both).
- Never paste resume text into tickets or logs. Use the resume id.
