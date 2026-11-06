# Runbook: evaluation

Run these from a checkout of the repository (the baseline and the dataset live in `evaluation/`).

```bash
uv run python -m pv_eval run
```
Runs the deterministic suites (free, no model) and prints every metric with its limit and baseline. Exit code 0 when everything holds, 1 when something does not.

```bash
uv run python -m pv_eval run --store
```
Also stores the report so Admin, Evaluation shows it and Health reports it. It needs the database settings in `.env`.

## The build failed on the evaluation gate
Open the failing test's message: it names the metrics that regressed. Then:
1. `uv run python -m pv_eval run` and read the table. The metric marked "regressed" or "below_limit" is the one.
2. Run `uv run python -m pv_eval run --json out.json` and open the failed cases (expected and got) in the file, or open the run on the Evaluation page if it was stored.
3. Decide. If the change made the check worse, fix the code. If the check is now right and the label or the baseline was wrong, say why in the commit.
4. Accepting a change is deliberate: `uv run python -m pv_eval run --update-baseline`, review the diff of `evaluation/baseline.json`, and commit it with the reason. Never update the baseline just to make a build green.

## A metric has no baseline
A new metric fails the gate until it has one. Run `--update-baseline`, read the value it wrote, and make sure it is what you expect before committing.

## The dataset test failed
The dataset no longer matches `evaluation/dataset/jobs-v1.json`. If you changed the generator or a label on purpose: bump `DATASET_VERSION` in `pv_eval/dataset.py`, run `uv run python -m pv_eval write-dataset`, then update the baseline, and review all three together. If you did not mean to, revert the change.

## Run the model suite
```bash
uv run python -m pv_eval run --llm --limit 10
uv run python -m pv_eval run --llm --store
```
Needs `GEMINI_API_KEY` and `LLM_MODEL`. It makes one or two model calls per posting (100 postings), so start with `--limit`. A call that fails counts against recall, so a provider outage shows as low recall, not as nothing. The limits are starting points. After the first full run, read the numbers, set the limits in `pv_eval/llm.py` from them, then `--llm --update-baseline` (C-149). Until a baseline exists this suite fails nothing.

## "The latest evaluation did not pass" on Health
Open Evaluation, choose the run, read the metrics marked in red and the failed cases. Compare with the previous run to see what moved. Fix, then store a new passing run (`--store`). A passing run after a failing one clears the alert.

## A failed case is the known limit
`injection_quoted` cases fail on purpose: a quoted injected sentence is real text in the posting, so grounding keeps it. The metric is bounded at 1.0 and the person sees the sentence with its quote. If this number ever drops, grounding improved; update the baseline.

## What to look at
- Table `evaluation_runs` (system table, append-only for the application, no personal data).
- `evaluation/baseline.json` (accepted numbers), `evaluation/dataset/jobs-v1.json` (the saved dataset).
- Limits for the deterministic suites are in `pv_eval/suites.py`. Rules for labels are in `docs/evaluation/labeling-guidelines.md`.
