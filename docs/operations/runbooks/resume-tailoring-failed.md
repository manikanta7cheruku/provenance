# Runbook: Resume suggestions fail, stay empty, or look wrong

A person presses "Suggest changes" in the studio and sees "No suggestions this time", an endless "Looking for changes", no suggestions at all, or suggestions that are all blocked.

## Detection
- The "Tailor to a job" section of the studio (state and message).
- Admin, Runs: `resume_tailoring` runs that are failed, retrying, or running for a long time.
- `llm_calls` with purpose `tailor_resume` and a non-ok status (no text is stored).
- `resume_tailorings.status`, `error_code` and `model_calls` for the resume and job.

## Diagnosis
| What the person sees | Meaning | Action |
|---|---|---|
| The suggestion service is not set up yet | No `GEMINI_API_KEY` on the worker (`AI_NOT_CONFIGURED`) | Set the key, restart the worker, ask them to press "Suggest again". `.\scripts\pv.ps1 ai-check` |
| The suggestion service did not answer | The provider stayed down through every attempt (`AI_UNAVAILABLE`) | Check the provider status and `LLM_MIN_INTERVAL_SECONDS`. Nothing in the resume was changed |
| Check this job against your profile first | The job has no finished evidence check (`ANALYSIS_NEEDED`) | Ask them to run "Check my evidence" on the job page |
| "No changes suggested" | The model found nothing clearly better, or the resume has no bullets or summary to reword, or the check confirmed no requirement | Look at the job's evidence check. A resume with only headings has nothing to tailor |
| Every suggestion is blocked | The model keeps adding words from the job that the evidence does not contain | Expected when the profile is thin. Add the missing detail to the profile, check the job again, ask again. Repeats across many people point to a prompt or model change: look at `prompt_version` |
| "That part of your resume changed after this was suggested" | The person edited that part after the suggestion was made | Ask for new suggestions |
| Stuck on "Looking for changes" | The task is queued or waiting for a retry | `.\scripts\pv.ps1 queue`, then worker logs. See [stuck task](stuck-task.md) |

## Mitigation
The resume is never changed by a failed or empty run: the task does not write to it. Accepting a suggestion is a normal save with a restore point, so it can be undone from Earlier versions.

## Recovery
After fixing configuration the person presses "Suggest again". It replaces the old suggestions. A task dead-lettered for `tailor_resume` holds no secret and can be requeued from Admin, System. Do not edit `tailoring_suggestions` by hand.

## Prevention
Run `python -m pv_llm.check` after any key or model change. Do not paste resume, evidence or job text into tickets: use the resume id, job id and the counts.
