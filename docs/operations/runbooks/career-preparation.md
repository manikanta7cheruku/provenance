# Runbook: career preparation

## "Check this job first"
Preparation is built from the evidence check. The person opens the job and runs the check. Until it is complete nothing generated is offered. The overview, plan and company notes are still available.

## A piece of material says "The writing service is not set up yet"
No model key is configured (`GEMINI_API_KEY`, `LLM_MODEL`). The overview, plan, progress, company notes and mock interview do not need one. See [the real model setup](../../carryover/real-ai-model-setup.md).

## "The writing service did not answer" or "gave an answer we could not use"
Provider trouble is retried up to four times, then shown. The person presses Write again. If it keeps happening look at the task in Admin (`prepare_job`) and the run steps (load, write, verify). The prompt version is stored on the output (`prepare-1`). A bad-output failure usually means the model did not return the JSON shape. Check `llm_calls` for the error class.

## "Your evidence does not support this yet, so there is nothing true to build it from"
A message (outreach, referral) or questions about the resume or projects need evidence the check found. The person adds evidence to the profile and checks the job again.

## An item says "not enough evidence"
This is the product working. The requirement is not shown by the profile, so the guidance explains the idea in general terms and nothing says the person has done it. It is a prompt to add evidence or to learn.

## A person says the guidance claims something untrue
Every item lists the claims that are not in the evidence or the job ("Not in your evidence"). If something untrue is not listed, that is a bug in the claim check (`pv_domain.tailoring.verify_text`), not in the screen. Keep the output id (not its text), reproduce with a stub, and add a test case.

## The mock interview scored an answer oddly
The feedback is a rubric computed from the answer (`pv_domain.preparation.score_answer`), not a judgement. It rewards situation, action and result words, numbers and named tools, overlap with the requirement, and it names claims not in the profile. It is blunt on purpose. Change it only with a test and bump `RULES_VERSION`.

## Rules changed
The priority and difficulty rules are `prep-rules-1`. A change goes in `pv_domain.preparation`, with the tests that show the example in the requirements document, and a new version string.

## What to look at
- Task type `prepare_job` in the task list, and its run steps.
- Audit event `career_preparation.started` (action only, no text).
- Tables `prep_outputs`, `prep_progress`, `job_preparations`, `mock_interviews` are tenant data with Row Level Security. Never query them without a tenant.
