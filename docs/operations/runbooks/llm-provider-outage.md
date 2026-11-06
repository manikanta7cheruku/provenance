# Runbook: model provider outage

## Detection
Health: "Many model calls are failing" (warning), the Model provider part shows a high failure share, runs end with "The writing service was busy or could not be reached", or the provider status page shows an incident.

## Diagnosis
1. Cost and usage: which operation and which error class (`TRANSIENT`, `PERMANENT`, a quota or key error)?
2. Find a run: paste a failed run reference to see the model calls and their error class.
3. Is it the provider or us? `uv run python -m pv_llm.check` (or the same inside the API container) makes one small call and says what came back. A key or model-name error shows here at once.
4. The provider status page, and your quota on it (a 429 means a rate or daily quota, not an outage).

## Mitigation
- Retries are automatic and bounded (the task backs off up to four times). Do nothing for a short blip.
- A rate limit or quota: set `LLM_MIN_INTERVAL_SECONDS` higher so calls are spaced, or wait for the quota to reset, or raise the quota with the provider.
- A bad key or model name: fix `GEMINI_API_KEY` or `LLM_MODEL` and redeploy.
- A long outage: tell people plainly. Reading, editing, exporting, the workbench and the mock interview do not need a model and keep working. Features that need a model say "not available right now" and can be retried.

## Recovery
Failed runs show "retry available". People press the button again, or you can requeue dead letters of type `analyze_job`, `tailor_resume`, `draft_application`, `prepare_job` from Queue once the provider is back. A failure is never counted twice: the quota key makes a retry of the same request free.

## Prevention
A daily spend ceiling and the alerts, a paid plan with a quota that fits real use, and a second provider behind the same interface (the provider is a Protocol) if outages become common.
