# Runbook: A pasted job could not be read

Users see "This posting could not be read" on the job page with a plain reason. The posting is saved. Nothing else is affected.

## Detection
- The job page state and message (`error_code` on the job).
- Admin, Runs: `job_extraction` runs with status failed.
- `llm_calls` rows with purpose `job_extraction` and a non-ok status (no text is stored).

## Diagnosis
| Message to the user | Code | Meaning | Action |
|---|---|---|---|
| The reading service is not set up yet | `AI_NOT_CONFIGURED` | No `GEMINI_API_KEY` on the worker | Set the key, restart the worker, ask the user to press "Read it again". `.\scripts\pv.ps1 ai-check` |
| The reading service did not answer | `AI_UNAVAILABLE` | Timeouts, 429 or 5xx on every attempt | Check the provider status and `LLM_MIN_INTERVAL_SECONDS`. The task retried before showing this |
| The answer could not be understood | `AI_BAD_OUTPUT` | Output failed the schema twice | Usually a one-off. Read again. If it repeats for many postings, check the prompt version and model name |
| No requirements found | `NO_REQUIREMENTS` | Nothing in the output could be found in the text | Ask the user to paste the full description, not a summary or a link |

## Mitigation
Users keep their saved postings. Eligibility on already-read jobs keeps working because it needs no model.

## Recovery
After fixing configuration, users press "Read it again". Do not edit `job_postings` by hand. A task stuck in reading: see [stuck task](stuck-task.md).

## Prevention
Run `python -m pv_llm.check` after any key or model change. Do not paste posting text into tickets: use the job id.
