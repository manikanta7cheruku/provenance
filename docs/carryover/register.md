# Carryover register

State: `open`, `closed (date)`, or `dropped (reason)`. Phase.Checkpoint is the one that created the item.

## A. Real AI model (needs a key)
The product runs end to end without a key and says so honestly. These items need a real model. See [real-ai-model-setup.md](real-ai-model-setup.md).

| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-01 | 1.6 | Resume parsing with a real model | Only a scripted stand-in and mocked transport were run | Upload your own text PDF with a key set. Compare entries to the resume. Record how many fields were wrong or missing | open |
| C-02 | 1.7 | Meaning search with a real embedding model | No key was configured, so quality and the 768 dimension support were not measured | `ai-check`, set `LLM_EMBEDDING_MODEL` (768 dimensions), run `embeddings`, try 10 searches that share meaning but not words | open |
| C-03 | 1.8 | Job reading on real postings | Extraction quality was tested on ten fixtures with a scripted provider | Paste three real postings. Check requirements, quotes and facts against the text | open |
| C-04 | 1.9 | The evidence agent on a real model | Verdict quality, real calls per job and free-tier timing are unmeasured | Check three real jobs. Record the verdicts you disagree with, model calls per job and the time | open |
| C-05 | 1.9 | The LangGraph comparison planned in ADR-0004 | Not run (stated in ADR-0032) | Optional. Build the same loop in the framework and compare code size and failure handling. Decide whether to keep the hand-built loop | open |
| C-06 | 2.4 | Tailoring suggestions on a real model | All tests use a stand-in. How useful they are, and how often the check blocks, is unmeasured | Tailor your resume to three checked jobs. Count useful, blocked and wrong suggestions | open |
| C-07 | 2.4 | An evaluation set of unsupported claims | Named in the roadmap and ADR-0036. Not built | Write 50 resume parts with a known invented fact and 50 honest rewordings. Measure how many invented facts the check catches and how many honest changes it blocks | open |
| C-08 | 1.9, 2.4 | Evaluation plan runs | The seed evaluation set covers rules, not model quality | Follow [evaluation-plan.md](../evaluation/evaluation-plan.md) with the real model | open |

## B. A real person using it
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-10 | 2.1, 2.2, 2.3 | The owner uses the studio for real | Builds were tested by machines and screenshots | Make your real resume in the studio, on a template, with the canvas. Write what felt slow, confusing or missing | open |
| C-11 | 2.3 | The template gallery with real content | Only sample words and two templates were looked at by eye | Open all 24 templates with your content and look at each page and PDF | open |
| C-12 | 2.4 | The tailoring review screen | Nobody has used it | Tailor to a real job. Note what was unclear | open |
| C-13 | 1.5, 2.2, 2.3, 2.4 | A screen reader session | Only axe and labels were checked | Use NVDA or Narrator on the shell, the canvas keyboard flow, the gallery and the review screen | open |
| C-14 | 1.5 | Firefox, Safari, real touch devices | Tested in Edge only | Open the main screens in each and note breakage | open |

## C. Technical gaps
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-20 | 2.1 | Several people rendering PDFs at once | Not measured | Start 5 exports together and record the time and failures | open |
| C-21 | 2.1 | Names in non-Latin scripts in PDFs | The shipped fonts are Latin only | Try Devanagari, Tamil and Arabic names. Decide on extra fonts | open |
| C-22 | 2.1 | Editor library comparison with Lexical | Not run | Optional. Prototype the same toolbar in Lexical and compare | open |
| C-23 | 2.2 | Dense full-page text and other fonts in the PDF match check | The spike used five layouts | Repeat the spike with a full page and each font pair | open |
| C-24 | 2.3 | Three full pages in every template with real fonts | Pages were checked with stand-in measurements | Load a long resume in each template and print | open |
| C-25 | 2.3 | How real tracking systems read the templates | The ATS label is the product's own check | Test the PDFs in a free resume parser or two and record the results. Do not claim vendor behavior | open |
| C-26 | 2.4 | Tailoring on a canvas resume with many text boxes in a real browser | Only guided resumes were used in the browser | Tailor a canvas resume and accept several changes | open |
| C-27 | 2.4 | Accepting a suggestion drops bold and links inside the rewritten lines | A known limit | Decide whether to keep marks, and add it if yes | open |
| C-28 | 2.4 | Lowercase tools the job never names are not detected as claims | A known limit of the check | Measure with C-07 and widen the check if the set shows misses | open |

## D. Features asked for and scheduled
| ID | Phase.Checkpoint | Item | State |
|---|---|---|---|
| C-30 | 2.11 | Images, photos and icons on the canvas | scheduled |
| C-31 | 2.12 | Touch and phone editing | scheduled |
| C-32 | 2.13 | Saved themes and brand kit | scheduled |

## E. Source verification and search (added at 2.5)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-33 | 2.5 | Search sentences on a real model | The sentence parser was tested with a stand-in | Type 10 searches on Find jobs with a key set. Record wrong roles, places, companies or sources | open |
| C-34 | 2.5 | Owner confirms the source records | Lever is marked verified from documentation read by the build assistant. Greenhouse and Ashby terms could not be located or read in full | Read the current terms for Lever, Greenhouse and Ashby. In Admin (`PATCH /admin/sources/{key}`) set status, date, reviewer and notes. Do this before checkpoint 2.6 builds an adapter | open |
| C-35 | 2.5 | Decide on Remotive and Adzuna | Remotive bans displaying jobs to collect sign-ups and the product needs accounts. Adzuna needs a licence for commercial use | Ask each provider, or decide to skip them. Record the decision in the provider file and the registry | open |
| C-36 | 2.5 | Read the unread terms | Naukri returned 403. About 149,000 characters of Indeed's terms were not read | Read them in a browser and update the records and [import-only-platforms.md](../providers/import-only-platforms.md) | open |
| C-37 | 2.5 | Adzuna India coverage | The official pages read do not list countries | Check the interactive documentation in a developer account | open |
| C-38 | 2.5 | A larger company list and verified board ids | 24 companies, three with confirmed boards | Add the companies you care about to `registry_data/companies.json`. Confirm a board exists before adding its id | open |
| C-39 | 2.5 | Review dates | Every verification expires after 180 days | Put a reminder at 2027-04-30 to re-read each enabled source | open |

## G. Fetching and source health (added at 2.6)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-50 | 2.6 | A live poll through the whole path | Nothing is enabled, so the poller has never used the real network. Tests use a fake fetcher and saved real answers | After C-34, record Lever's review in Admin and enable it (see [source-health runbook](../operations/runbooks/source-health.md)). Check the fetch log shows `ok` with new jobs, then Find jobs lists them | open |
| C-51 | 2.6 | Greenhouse and Ashby cannot be used yet | Their adapters are built, but their terms are unverified | Read their terms (C-34). If they allow it, record the review and enable. If not, leave them off or remove the adapters | open |
| C-52 | 2.6 | The weight of a big board | A Greenhouse board with full descriptions was 5.8 MB, an Ashby board 2.9 MB, per poll | Watch `bytes_read` in the fetch log for a week. If it matters, poll the list without content and fetch only changed jobs | open |
| C-53 | 2.6 | A retention rule for fetched job text | The terms read state no retention rule. Closed jobs are kept | Decide how long closed jobs are kept and add a cleanup. Check each source's terms again | open |
| C-54 | 2.6 | Behavior over days | Intervals, the breaker and chaining were tested with a fake clock | Leave Lever enabled for a few days. Read the log for skips, failures and breaker events | open |
| C-55 | 2.6 | Remotive and Adzuna adapters | Waiting for the owner decisions in C-35 | After the decisions, build an adapter for each source that stays | open |
| C-56 | 2.6 | The shape fixtures age | They are one day's real answers (2026-11-02) | When a source reports `bad_response`, read a fresh answer, update the fixture and the parser | open |

## F. Production and deployment (Phase 3)
| ID | Phase.Checkpoint | Item | State |
|---|---|---|---|
| C-40 | 3.7 | Production object storage (Cloudflare R2) | open |
| C-41 | 3.7 | Production email provider (Resend or Brevo) | open |
| C-42 | 3.7 | Paid-tier model decision and budget | open |
