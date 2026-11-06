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
| C-28 | 2.4 | Lowercase tools the job never names are not detected as claims | A known limit of the check | Measure with C-07 and widen the check if the set shows misses | Closed in the carryover sweep: a lexicon of common tools is a claim in any case (`TOOL_LEXICON`). Tools outside the lexicon still need the job to name them. |

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
| C-53 | 2.6 | A retention rule for fetched job text | The terms read state no retention rule. Closed jobs are kept | Decide how long closed jobs are kept and add a cleanup. Check each source's terms again | Closed in the carryover sweep: the worker deletes closed listings older than `CLOSED_JOB_RETENTION_DAYS` (90). |
| C-54 | 2.6 | Behavior over days | Intervals, the breaker and chaining were tested with a fake clock | Leave Lever enabled for a few days. Read the log for skips, failures and breaker events | open |
| C-55 | 2.6 | Remotive and Adzuna adapters | Waiting for the owner decisions in C-35 | After the decisions, build an adapter for each source that stays | open |
| C-56 | 2.6 | The shape fixtures age | They are one day's real answers (2026-11-02) | When a source reports `bad_response`, read a fresh answer, update the fixture and the parser | open |

## H. Duplicates and links (added at 2.7)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-60 | 2.7 | Matching thresholds on real data | The thresholds (text agreement 0.35, 0.6, 0.9, title closeness 0.82) were chosen and tested on constructed jobs | After two sources are polled and you have pasted real jobs, review `GET /admin/job-links` and your matches. Record wrong links and missed duplicates, then adjust `pv_domain/dedupe.py` with a test for each | open |
| C-61 | 2.7 | Cross-source matching on live data | Only Lever can be switched on, so there is one live source | After C-34 confirms Greenhouse or Ashby, poll two sources for one company and look at the links | open |
| C-62 | 2.7 | Company name variants | Companies match after case, punctuation and legal suffixes only. Google LLC and Alphabet are different | Add aliases to `registry_data/companies.json` for the companies you care about, and use the registry canonical name for matching | Closed in the carryover sweep: more aliases in the company seed (brand and legal names). Still a seed list, not a live source. |
| C-63 | 2.7 | Place name variants | Places are compared by words and country names. Bengaluru and Bangalore are different | Add a small place alias list (India first) with tests | Closed in the carryover sweep: `pv_domain.places` maps known alternative city names, used by duplicate detection and eligibility. |
| C-64 | 2.7 | A screen to review suggested links | Administrators have an API only | Build a small admin page if suggested links turn out to be common | open |
| C-65 | 2.7 | Many candidates for one company | Candidates are capped at 400 per comparison | If a company has more open jobs than that, compare by title first | Closed in the carryover sweep: candidates are ordered by title similarity before the 400 cap. |

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

## J. The workbench (added at 2.9)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-73 | 2.9 | A salary filter | The reader does not extract salary yet, so there is nothing to filter on | When a real model is set up (C-01), add salary to the extraction prompt and facts with a quote check, then add the filter | open |
| C-74 | 2.9 | Fit for jobs that have not been checked | Fit shows "Not checked yet" until the evidence check runs on a job | Use the workbench for a week with a real model. If the blank column is annoying, offer "Check these jobs" as a bulk action | open |
| C-75 | 2.9 | Drawer at medium width and structured rows on compact | Below the wide width the job page opens instead of a drawer, and the table scrolls inside its region | Try the workbench on a tablet and a phone, then build the drawer and compact rows from the UX specification | open |
| C-76 | 2.9 | Screen reader and keyboard pass of the workbench | Axe and keyboard tests pass. No screen reader has been used on it | Do the manual pass at 3.7 with NVDA and VoiceOver on the list, the pane, bulk actions and the dialogs | open |
| C-77 | 2.9 | Lists past 500 jobs | The list is cut at 500 and loads everything for the person on each request | If a real list grows past a few hundred, add paging and move the filters into SQL | open |
| C-78 | 2.9 | A dismiss reason as feedback | The UX specification asks for an optional reason stored as feedback. The private note is used instead | Decide whether a reason list is worth it once there is something to learn from it | open |
| C-79 | 2.9 | Approve for preparation does nothing yet | It records intent. Preparation arrives in Phase 3, and approval cannot be withdrawn except by dismissing | When preparation is built, decide whether approval can be withdrawn and what it starts | open |

## K. The shortlist email and application drafts (added at 2.10)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-80 | 2.10 | Drafts from a real model | Cover notes and answers were proven with a stand-in. The prompt `draft-1` has not met a real model | After C-01, write 10 cover notes and answers for real checked jobs. Read each. Record invented facts, flat writing and anything that sounds like every other cover note, then tune the prompt with a test per case | open |
| C-81 | 2.10 | The shortlist in a real inbox | Mail was proven with a stand-in server. Delivery, spam placement, SPF and DKIM and how it reads are untested, and there is no one-click unsubscribe (the email links to the settings page, which needs a sign-in) | At deployment (3.x) set up a sending domain with SPF and DKIM, send a few to your own inboxes and read them, and add a List-Unsubscribe header with a signed one-click link if it matters | open |
| C-82 | 2.10 | Only jobs the person added are shortlisted | Jobs found by polling are not in the email unless the person adds them | After using it for a few weeks, decide whether found jobs that match your profile should be shortlisted too | open |
| C-83 | 2.10 | A rare duplicate email | Delivery is at least once, so a crash between sending and recording can send one twice | Accept it, or record the mail provider message id and check it before sending | open |
| C-84 | 2.10 | How good the claim check is on real drafts | It checks numbers, names and job words against the evidence and the job heading. It does not understand meaning, so a paraphrase that changes a fact is not caught, and an honest name that is not in the cited evidence is flagged | With real drafts (C-80) count how many honest drafts are flagged and how many false claims get through. Add a test for each and adjust `pv_domain/drafts.py` or `tailoring.py` | open |
| C-85 | 2.10 | Drafts use only the evidence cited by the check | The resume and the rest of the profile are not used, so a draft can leave out something true | Decide whether to add the person's own resume text as a source after reading real drafts | open |
| C-86 | 2.10 | More tracker features | Applications show days since applied. There are no follow-up reminders, interview stages or a timeline | Use the Applications view for a real search, then decide what to add | open |
| C-87 | 2.10 | A shortlist across a real change of clocks | The next time is tested across the change for several zones, but no real email has been sent across one | Leave the email on across the next change of clocks in your zone and check the hour | open |

## L. Pictures and icons (added at 2.11)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-88 | 2.11 | Photos from a real phone | Pictures were tested with files made in the tests. HEIC (an iPhone default) is refused, and orientation and color profiles from real phones are untested | Upload five real photos from your phone and a camera. Check orientation and color. Decide whether HEIC should be accepted (it would need a decoder) or the message is enough | open |
| C-89 | 2.11 | A real PDF with a picture | The PDF tests stand in for the engine, and the PDF tests that need WeasyPrint run only in Docker | Export a resume with a picture and an icon. Open it in two PDF readers. Run it through a free applicant tracking checker and see what it reads | open |
| C-90 | 2.11 | Crop and rotate by dragging | Crop is two position numbers and there is no rotate | Use it for a week and decide whether drag-to-crop and rotate are worth building | open |
| C-91 | 2.11 | Templates with a picture slot | No template uses a picture, they are added by hand | Decide whether one or two templates should have a photo or logo slot, keeping the ATS-safe ones text only | open |
| C-92 | 2.11 | Pictures stuck in old versions | A picture in a saved version cannot be deleted until its resume is deleted | If people want to remove an old photo, add a way to remove it from old versions or to purge old versions | open |
| C-93 | 2.11 | More icons | Sixteen icons, no search, no brand marks | Add icons people ask for, each with a golden test | open |
| C-94 | 2.11 | A screen reader pass of the picture screens | Axe passes. The dialogs and the properties have not been used with a screen reader | Do it at 3.7 with NVDA and VoiceOver | open |
| C-95 | 2.11 | Decode pictures in a separate process | The decoder runs in the API process behind size and pixel limits | At deployment (3.x) run `process_image` in a short-lived sandboxed process or in the worker with a memory and time limit | open |

## M. Touch and phone editing (added at 2.12)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-96 | 2.12 | Try it on a real phone and tablet | The tests emulate touch events in a desktop browser | Open the studio on your phone and tablet. Drag, pinch, double tap, use the selection bar and the properties. Note anything awkward | open |
| C-97 | 2.12 | iOS Safari | Touch handling differs in Safari (pinch and scroll rules) | Test on an iPhone and an iPad | open |
| C-98 | 2.12 | Pick several elements by touch | The selection box is a mouse tool because it competes with scrolling | Decide whether a select mode or a long press is worth it | open |
| C-99 | 2.12 | Screen reader on a phone | Axe passes. TalkBack and VoiceOver were not used | Do it at 3.7 | open |
| C-100 | 2.12 | Drag to resize on small elements | The 44 pixel handle targets overlap on very small elements | Use it for a week. If it bites, add a resize mode or bigger minimum handles | open |

## N. Saved themes (added at 2.13)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-101 | 2.13 | Use themes on real resumes | Tested with made-up themes | Save a look you like, apply it to a second resume, change it and update the theme. Note what is missing | open |
| C-102 | 2.13 | Apply a theme to every resume at once | One resume at a time | Decide whether you need it once you have several resumes | open |
| C-103 | 2.13 | Themes older than a rule | A rule added later could refuse an old theme when applied | If the color rules change, add a check or a migration that lists themes that no longer pass | open |
| C-104 | 2.13 | Screen reader pass of My themes | Axe passes, no screen reader was used | Do it at 3.7 | open |

## O. Design foundation (added at 3.8)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-105 | 3.8 | Confirm the palette by using it | It was chosen by reasoning and measurement, not by living with it | Use the product for a few days in light and dark. Say what you would change. It is one file | open |
| C-106 | 3.8 | Colors on real displays | Checked by arithmetic, not on devices | Look at the gallery on a phone, a laptop and an external monitor, in daylight and at night | open |
| C-107 | 3.8 | Color-blindness check | Status never depends on color alone, but no simulation was run | Run each main screen through a color-blindness simulator | open |
| C-108 | 3.8 | A real designer's review | The direction is written and tested, not reviewed by a designer | Ask a designer to review the gallery and the voice guide before 3.10 | open |

## P. The resume experience (added at 3.9)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-109 | 3.9 | A usability session | No real person has used the new start screen and editor | Watch three people (not you) start a resume and make five edits without help. Write down where they stop. Fix before 3.10 ends | open |
| C-110 | 3.9 | Drag to reorder layers and sections | Reordering is by buttons and commands only. A drag with a keyboard equal was not built | Decide whether to build it once you have watched real use | open |
| C-111 | 3.9 | Screen reader pass of the palette and start cards | Axe passes. NVDA, VoiceOver and TalkBack were not used | Do it at 3.10 | open |
| C-112 | 3.9 | Speed on a slow machine | The budget was measured on a development machine | Try an older laptop and a mid-range phone with a long resume | open |
| C-113 | 3.9 | The guided editor | Only its start screen changed. Its editing screens are the older design | Rebuild them in 3.10 or retire the guided mode if the free canvas with the layout check covers it | open |

## Q. Whole-product polish (added at 3.10)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-114 | 3.10 | Owner review of every screen | The polish is a first pass by reasoning and screenshots. The owner has not judged it | Walk every screen in light and dark, on a laptop and a phone, and list what to change. These become the next changes | open |
| C-115 | 3.10 | The workbench and job detail layouts | They inherit panels, controls and states, but their internal layout is the older design | Redesign them once the owner has said what feels wrong | open |
| C-116 | 3.10 | The order of the Opportunities page | Adding a job comes before the list of jobs. The list is probably the better first thing | Decide with the owner, then reorder | open |
| C-117 | 3.10 | A screen reader pass of the whole product | Axe passes everywhere. NVDA, VoiceOver and TalkBack were not used | Do it at 3.7 | open |
| C-118 | 3.10 | Usability sessions | No real person has used the product in this look | Watch three people do the main journeys. Fix what stops them | open |
| C-119 | 3.10 | A dark navigation sidebar | Deferred in ADR-0046 and ADR-0048 | Decide after the owner has lived with the light one | open |

## R. The GitHub connection (added at 3.1)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-120 | 3.1 | Create the GitHub OAuth app and connect for real | The connection was built and tested against a test double. Nothing has been exercised against github.com | Follow docs/providers/github.md (setup), put the client id and secret in `.env`, restart, connect your own account, choose two repositories, check the entries, disconnect, and check the app is gone at github.com/settings/applications | open |
| C-121 | 3.1 | Real READMEs | The README reduction was tested on written examples, not on a variety of real repositories | After C-120, look at the entries made from ten different repositories. Note any that read badly and add a test case for each | open |
| C-122 | 3.1 | A managed key for the token key | The sealing key is derived from the application secret. Rotating that secret disconnects everyone | At deployment (3.7) move the key into a managed key store with versions, keeping the `v1.` format and adding `v2.` | Closed at 3.7: the token key ring. |
| C-123 | 3.1 | Other evidence platforms | LeetCode, CodeChef, GeeksforGeeks and similar have no connector and their terms were not read | If you want them, read their terms and API pages and decide per platform. Until then they use the by-hand path | open |
| C-124 | 3.1 | A screen reader pass of the GitHub panel | Axe passes. No screen reader was used on the repository list and the disconnect question | Do it at 3.7 | open |

## S. Career preparation (added at 3.2)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-125 | 3.2 | Written material on a real model | Questions, guidance, messages were tested with a stub model | With a key set, write every kind for three real jobs. Read every item. Count items the claim check missed and items that read as flattery. Record the result | open |
| C-126 | 3.2 | The mock interview rubric on real answers | The rubric was tested on written examples | Answer five questions as you really would and see whether the scores and notes feel fair. Note answers it misjudges and add test cases, then bump the rules version | open |
| C-127 | 3.2 | Company research and learning resources | The company section shows only what the posting states and the person's notes. No resource links exist | Decide which official company sources to allow, then build the fetch through the hardened fetch layer with source and time shown. Build a curated list of real learning resources and keep it current | open |
| C-128 | 3.2 | Real people practising | No one has used preparation or the mock interview | Watch three people use it for one real job. Note where they stop. Fix before launch | open |
| C-129 | 3.2 | A screen reader pass of preparation | Axe passes. No screen reader was used on the tabs, the disclosures and the mock interview | Do it at 3.7 | open |
| C-130 | 3.2 | A model written follow-up in the mock interview | Feedback is a rubric. A model follow-up could probe an answer | Only if the evaluation set (3.6) shows it helps and the claim check keeps it honest | open |

## T. Plans and quotas (added at 3.3)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-131 | 3.3 | Measure real cost, then set the limits | The Free, Starter and Pro numbers are starting points chosen before any cost was measured. Failed generations are counted and not refunded, deep evidence search is not metered separately, and the shortlist email stays enabled on Free | With a real model key, run a typical month for a few people, read the cost per unit, then change the `plans` rows in a migration. Decide on refunds for failures | open |
| C-132 | 3.3 | Choose a payment provider | Payments are a disabled interface. No provider terms were read | Compare providers (fees, tax handling, regions, refund rules), read the terms, implement `PaymentProvider`, test with the provider's test mode, then add a webhook with signature checking | open |
| C-133 | 3.3 | A screen reader pass of the plan section | Axe passes. No screen reader was used on the meters and the comparison table | Do it at 3.7 | open |

## U. Reports (added at 3.4)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-134 | 3.4 | Open the reports in real applications | The Excel and Word files are written by hand and were opened with openpyxl and python-docx, not the real programs | Make one workbook and one Word report with quotes on. Open each in Excel, Word, LibreOffice and Google Sheets or Docs. Check the sheets, the frozen header, the filters, the table and the fonts. Note anything that looks wrong and add a test for the structure | open |
| C-135 | 3.4 | A report PDF | The requirements list a PDF report. Only CSV, XLSX and DOCX were built. The resume PDF exists | Design a report template and make it with the existing PDF engine, then add it as a fourth format | open |
| C-136 | 3.4 | A compensation column | Compensation is not extracted from postings, so the report has no such column | When extraction reads pay, add the column to the model, the three writers and the tests | open |
| C-137 | 3.4 | Sweep expired reports and delete them with the account | Expired and surplus reports are removed when a person lists or asks for reports. A person who never returns keeps their file until then | Add a scheduled sweep task, and include report files in the account deletion workflow (T20) at 3.7 | Closed: the worker sweeps expired reports hourly (carryover sweep), and account deletion removes them (3.7). |
| C-138 | 3.4 | A screen reader pass of the export panel | Axe passes. No screen reader was used on the panel, the status changes and the download links | Do it at 3.7 | open |
| C-139 | 3.4 | Short-lived signed links | Downloads need the signed-in session. Signed links need object storage | At 3.7, when files move to object storage, return a signed link that expires in minutes and keep the session check | open |

## V. Observability and the console (added at 3.5)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-140 | 3.5 | Set alert thresholds from measurement | The limits (queue age, failure streaks, error rates, slowness, failed sign-ins) were chosen before there was traffic | After a few weeks of real use, read the Health and Cost pages, find the normal range for each, and change `pv_domain.alerts.Thresholds` with a test | open |
| C-141 | 3.5 | Deliver alerts to a channel you read | Alerts show on the console and in `check-alerts`. Nothing is pushed | At 3.7 choose a channel (email, chat or a pager), run `check-alerts` on a schedule or from a monitor, and send only new critical alerts | Closed in the carryover sweep: alert emails to administrators with a cooldown. Off until `ALERT_EMAIL_ENABLED` is set; needs a real mail provider (C-41). |
| C-142 | 3.5 | Request statistics across processes, and tracing | Timings are kept in each API process and reset on restart. No distributed tracing. SSRF rejections are not counted anywhere | At 3.7 export metrics to a shared store, add trace spans keyed by run id, and record SSRF rejections as security events | open |
| C-143 | 3.5 | Cost by plan, and cost per unit | The plan is in a tenant table, so cost cannot be added up by plan without crossing the admin boundary | Record the plan on each model call (a column on `llm_calls`), then add cost by plan. This is needed to close C-131 | Closed in the carryover sweep: the plan is recorded on each model call and cost is added up by plan. |
| C-144 | 3.5 | The latest evaluation summary | The requirements list it. There is no evaluation yet | Show it on Health when the harness exists (3.6) | Closed at 3.6: the evaluation summary shows on the console. |
| C-145 | 3.5 | Break-glass access | The requirements describe an audited, reasoned access to content. No admin route can read content, so none was built | Only if support ever needs it: a capability, a stated reason, an audit event visible in the log | open |
| C-146 | 3.5 | A screen reader pass of the console and the run page | Axe passes. No screen reader was used on the tables, statuses and forms | Do it at 3.7 | open |
| C-147 | 3.5 | Database, disk, connection and backup alerts | They need the deployment (3.7) and a backup process | Add the snapshot fields and rules when production exists | Partly closed in the carryover sweep: a connections alert. Disk and backup alerts still need the deployment. |

## W. The evaluation harness (added at 3.6)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-148 | 3.6 | Real postings labeled by people | The dataset is synthetic and its labels are true by construction. It shows our checks behave as written, not how a real model reads real postings | Collect 50 to 100 real postings with permission, remove the company and any person, write the labels under the guidelines (someone other than the author of the extraction), and add them as a new dataset version with its own baseline | open |
| C-149 | 3.6 | A real-model baseline | The LLM suite was tested with stand-in models. It has never run against a real model, and its limits are starting points | With a key set, run `python -m pv_eval run --llm` on all 100 postings, read the numbers, set the limits in `pv_eval/llm.py` from them, then `--llm --update-baseline` and `--store` | open |
| C-150 | 3.6 | Generation and preparation metrics | Only the claim check is measured. Contradiction rate, human preference and preparation relevance and resource links are not | Add cases and a small human rating, with the claim check as the authority on facts | open |
| C-151 | 3.6 | Count the feedback labels | The learned-ranker decision needs the number of labels and of people. They are in a tenant table that administrators cannot read | Add an aggregate counter table kept by a trigger (a count and a distinct count, no content) and show it on the Evaluation page | Closed in the carryover sweep: label and people counters kept by triggers feed the ranker decision. |
| C-152 | 3.6 | Schedule the model run | The LLM suite is manual | At 3.7, run it weekly in its own job, store the result with trigger `scheduled`, and alert on a drop | open |
| C-153 | 3.6 | A screen reader pass of the Evaluation page | Axe passes. No screen reader was used on the tables and the selects | Do it at 3.7 | open |

## X. Production, security and your data (added at 3.7)
| ID | Phase.Checkpoint | Item | Why open | How to close | State |
|---|---|---|---|---|---|
| C-155 | 3.7 | A lawyer reads the privacy policy and terms | They are drafts that describe what the product does. They are not legal advice | Have a qualified person read both, add the company name, contact address and governing law, remove the draft banner, and decide whether sign-up needs an explicit tick and a record of the version accepted | open |
| C-156 | 3.7 | Breach notification duty | The runbook says to tell people and check the law. Which law applies and by when is not known | Decide with the lawyer who must be told (people, a regulator) and within what time, and write it into the runbook | open |
| C-157 | 3.7 | Confirm RPO and RTO | They are proposed (24 hours, 4 hours) and measured on a laptop | Decide the targets, and change backups (more often, or point-in-time recovery) if the data loss tolerated is smaller | open |
| C-158 | 3.7 | Drills on the real host | The nine drills ran on a laptop | Repeat drills 1, 2, 3b, 4, 5, 8 and 9 on the real host, add losing the machine and rebuilding, and update drills.md | open |
| C-159 | 3.7 | Point-in-time recovery | A nightly dump loses up to a day | If a day is too much, use a managed database with point-in-time recovery or continuous archiving | open |
| C-160 | 3.7 | Copy backups off the machine, automatically | Backups are written next to the data. A lost machine loses them | Schedule `deploy/backup.sh` nightly and copy the folder to another machine or a bucket, with the same 30 day rule. Test a restore from the copy | open |
| C-161 | 3.7 | A second person who can act | One operator is a single point of failure | Name a second person with access to the host, the password manager and the runbooks, and rehearse the tabletop together | open |
| C-162 | 3.7 | Restore one person's data | Only a whole restore exists | If support ever needs it, restore into a scratch database and copy that person's rows back, and write the runbook | open |
| C-163 | 3.7 | Image vulnerability scanning | Dependencies are audited, the operating system packages in the images are not | Add an image scanner (for example Trivy) to the `images` CI job and decide the severity that fails the build | open |
| C-164 | 3.7 | A penetration test | The author tested their own work | Have someone else test the production site before sign-up opens | open |
| C-165 | 3.7 | Bot protection on sign-up and sign-in | Rate limits and invites exist; a CAPTCHA or similar does not | Decide whether open sign-up needs it, and add it before opening sign-up | open |
| C-166 | 3.7 | A screen reader pass of Your data and the legal pages | Axe passes. No screen reader was used | Do it with the other passes | open |
| C-167 | 3.7 | Firefox and Safari | The browser suite runs in Chromium and Edge | Add Firefox and WebKit projects to the Playwright config, fix what differs | open |
| C-168 | 3.7 | Host, domain, mail provider, model plan | They are accounts and money | Follow docs/operations/going-live.md steps 1 to 4 (this also closes C-41 and C-42) | open |

## F. Production and deployment (Phase 3)
| ID | Phase.Checkpoint | Item | State |
|---|---|---|---|
| C-40 | 3.7 | Production object storage (Cloudflare R2) | open |
| C-41 | 3.7 | Production email provider (Resend or Brevo) | open |
| C-42 | 3.7 | Paid-tier model decision and budget | open |
