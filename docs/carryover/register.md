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
| C-29 | 2.3 | **Redesign the resume templates properly.** The 24 templates are variations of one layout engine and do not look professional. Owner feedback on 2026-11-04: they look like a mini project. Scope: real type scale and spacing, stronger header designs, fewer and better templates instead of many similar ones, previews checked by eye with real content, a review of each template by the owner, then the PDF checked for every one | open (done after the main build, by owner decision) |
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

## H. Duplicates and links (added at 2.7)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-60 | 2.7 | Matching thresholds on real data | The thresholds (text agreement 0.35, 0.6, 0.9, title closeness 0.82) were chosen and tested on constructed jobs | After two sources are polled and you have pasted real jobs, review `GET /admin/job-links` and your matches. Record wrong links and missed duplicates, then adjust `pv_domain/dedupe.py` with a test for each | open |
| C-61 | 2.7 | Cross-source matching on live data | Only Lever can be switched on, so there is one live source | After C-34 confirms Greenhouse or Ashby, poll two sources for one company and look at the links | open |
| C-62 | 2.7 | Company name variants | Companies match after case, punctuation and legal suffixes only. Google LLC and Alphabet are different | Add aliases to `registry_data/companies.json` for the companies you care about, and use the registry canonical name for matching | open |
| C-63 | 2.7 | Place name variants | Places are compared by words and country names. Bengaluru and Bangalore are different | Add a small place alias list (India first) with tests | open |
| C-64 | 2.7 | A screen to review suggested links | Administrators have an API only | Build a small admin page if suggested links turn out to be common | open |
| C-65 | 2.7 | Many candidates for one company | Candidates are capped at 400 per comparison | If a company has more open jobs than that, compare by title first | open |

## I. Imports and the fetch of a typed address (added at 2.8)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-66 | 2.8 | Read a real career page | The page reader was tested on constructed pages and a fake web server | Import a few real career page links (not LinkedIn or Indeed) and check the title, company and text. Record pages that give no text and decide whether a headless browser is worth it | open |
| C-67 | 2.8 | The network is the third layer of the address defence | The rules and the pinned connection are proven in tests. The worker host must also have no route to private ranges or the metadata address | At deployment (3.x), block the worker's outbound traffic to private, link local and metadata ranges at the network, and test it with a request to such an address from the worker | open |
| C-68 | 2.8 | Cost of reading a spreadsheet | 200 rows is 200 reading tasks the first time | With a real model set up (C-01), import a 50 row file, check the cost shown in the runs page, and decide whether rows should be read on demand or in a daily budget | open |
| C-69 | 2.8 | robots.txt and per host politeness for typed addresses | One page per request, limited per person, honest name, but robots rules are not read | Decide whether to read robots.txt and apply a per host gap, and add it to `pv_worker.safe_fetch` with tests | open |
| C-70 | 2.8 | Only the first sheet of a workbook, no dates | The reader gives text and numbers of the first sheet. A date cell is shown as its stored number | Add a sheet chooser and date formatting if real files need them | open |
| C-71 | 2.8 | Preview before importing | The report is shown after the import, not before | If people want to check rows first, add a dry run that returns the report without saving | open |
| C-72 | 2.8 | Importing on a phone | Not tried on a phone | Try the four ways on a phone during real use (2.12 covers touch editing, not this) | open |

## F. Production and deployment (Phase 3)
| ID | Phase.Checkpoint | Item | State |
|---|---|---|---|
| C-40 | 3.7 | Production object storage (Cloudflare R2) | open |
| C-41 | 3.7 | Production email provider (Resend or Brevo) | open |
| C-42 | 3.7 | Paid-tier model decision and budget | open |
