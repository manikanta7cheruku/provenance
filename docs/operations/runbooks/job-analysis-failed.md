# Runbook: A job check stopped early, or never finishes

A person presses "Check my evidence" and sees "Stopped early", or the progress stays at "N of M checked", or the page says a question is waiting and they cannot see it.

## Detection
- The "Your evidence" section of the job page (state and message).
- Admin, Runs: `job_analysis` runs that are failed, retrying, or running for a long time.
- `llm_calls` with purpose `evidence_agent` and a non-ok status (no text is stored).
- `job_analyses.status` and `error_code` for the posting.

## Diagnosis
| What the person sees | Meaning | Action |
|---|---|---|
| The checking service is not set up yet | No `GEMINI_API_KEY` on the worker (`AI_NOT_CONFIGURED`) | Set the key, restart the worker, ask them to press "Continue checking". `.\scripts\pv.ps1 ai-check` |
| The checking service did not answer | The provider stayed down through every attempt (`AI_UNAVAILABLE`) | Check the provider status and `LLM_MIN_INTERVAL_SECONDS`. Verdicts already earned are kept, and "Continue checking" does only what is left |
| Progress stuck at "N of M" and no error | The task is queued or waiting for a retry | `.\scripts\pv.ps1 queue`, then worker logs. See [stuck task](stuck-task.md) |
| "A question for you" but no question shown | The question was answered or skipped in another tab | Reload the page |
| Many requirements Not verified with "The reader named evidence that could not be confirmed" | The model keeps citing words that are not in the evidence | Check the prompt version and model name in the run. Repeats across many people point to a model change |
| Many Not verified with "The search limit was reached" | The model used all its steps without a verdict | Same: look at the model and at `model_calls` on `job_analyses` |

## Mitigation
The posting, the profile and every earned verdict are safe. Eligibility on the job page needs no model and keeps working.

## Recovery
After fixing configuration the person presses "Continue checking". It reads what is stored and checks only the rest. Do not edit `requirement_verdicts` by hand. A task dead-lettered for this type can be requeued from Admin, System, and holds no secret.

## Prevention
Run `python -m pv_llm.check` after any key or model change. Do not paste evidence or posting text into tickets: use the job id and the counts.
