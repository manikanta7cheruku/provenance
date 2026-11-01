# Setting up the real AI model

Everything below runs on your machine. The product works without a key and says "not set up" where a model is needed. These steps turn the real model on and say what to measure for each checkpoint that depends on it. Use only your own resume and data on a free tier.

## 1. Get and set the key
1. Create a Gemini API key from Google AI Studio (https://aistudio.google.com/). Read the current free tier limits and data terms there before pasting any personal data.
2. Put it in `.env` as `GEMINI_API_KEY`. Do not commit `.env`.
3. List the model names your key can use: `.\scripts\pv.ps1 ai-check`.
4. Set `LLM_MODEL` to a generation model from that list, and `LLM_EMBEDDING_MODEL` to an embedding model that supports 768 dimensions.
5. `.\scripts\pv.ps1 restart worker`, then `.\scripts\pv.ps1 up` if the stack was down.
6. Optional pacing for the free tier: `LLM_MIN_INTERVAL_SECONDS`.

## 2. What to do per checkpoint (see the register for the IDs)
| Checkpoint | Do this | Record |
|---|---|---|
| 1.6 (C-01) | Profile, upload your resume PDF, press Read it again | entries wrong or missing |
| 1.7 (C-02) | `.\scripts\pv.ps1 embeddings`, then search on Profile | whether meaning search finds matches that share no words |
| 1.8 (C-03) | Opportunities, paste three real postings | wrong or missing requirements, quotes not in the text |
| 1.9 (C-04) | Check my evidence on each job | verdicts you disagree with, model calls per job, minutes taken |
| 2.4 (C-06) | Studio, Tailor to a job | useful, blocked and wrong suggestions |
| 2.5 (C-33) | Find jobs, type a few natural language searches | wrong filters, wrong companies, wrong sources |

## 3. Cost and safety
- Every call is recorded in the usage ledger with its purpose and token counts. Check Admin, Runs.
- The model is never given another person's data. In these checks it only sees your own.
- If the free tier limits you, raise `LLM_MIN_INTERVAL_SECONDS` rather than retrying by hand.

## 4. When done
Write the dated result next to each item in [register.md](register.md). If quality is poor, record the example (ids and counts, no personal text) and decide on the model or prompt change as its own checkpoint.
