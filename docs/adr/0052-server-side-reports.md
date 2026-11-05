# ADR-0052: Server-side reports (CSV, Excel, Word)

Status: Accepted (checkpoint 3.4).

## Context
A person who tracks jobs wants to take them elsewhere: into a spreadsheet to sort and share, or into a document to read and edit. The requirements (export-reporting-requirements.md) ask for reports made on the server from stored data, never from the screen, that say when they were made, are limited to their owner, expire, and cannot carry a spreadsheet formula. The risks are a posting that plants a formula in someone's spreadsheet, a file another person can fetch, evidence text leaking into a file that is then shared, a file that will not open, and storage that fills with old reports.

## Decision

**One report model, three writers.** `pv_domain.report` builds a `Report` from stored data: when it was made (UTC), the filters that chose the jobs in words, the sources the jobs came from and how each came in, a counts sentence worked out from the stored jobs ("41 opportunities. 12 strong matches..."), the jobs, their requirements and the evidence behind each verdict. `pv_files.report_formats` writes that one model as CSV (UTF-8 with a byte order mark so Excel reads accents), an Excel workbook (Summary, Opportunities, Requirements, Evidence, with a frozen header row and filters) and a Word document (summary, a table of the jobs, then each job in turn). What a person sees in each is the same, and the same stored data gives the same report.

**The jobs are the ones the person was looking at.** The report is made with the filters of the workbench list (`pv_domain.pipeline.select`, the same code), stored cleaned on the row, so the file holds exactly what the list showed. Up to 500 jobs, the same limit as the list, and a report says when more matched.

**A cell is made safe before it is written, in the domain.** Characters XML forbids are dropped (one odd posting cannot make a file unreadable). A cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading apostrophe. Every string in a workbook is an inline string and no formula is ever written. The writers drop forbidden characters again as a second layer. The tests plant formula strings in the job itself and read the files back with real readers.

**The Office files are written by hand, not with a library.** An XLSX and a DOCX are ZIP files of small XML parts. Writing them with the standard library keeps the dependency list (and so the supply chain) unchanged, matches the reader in `pv_files.tabular`, and makes every byte ours: no macros, no external relationships, no links that fetch, a fixed timestamp inside the archive so the same report gives the same bytes. The cost is that "opens in Excel and Word" is something we verify, not something a library vouches for: the tests open every file with openpyxl and python-docx (test-only dependencies), and opening in the real applications is a carryover.

**Evidence quotes are off by default.** A quote is a line from the person's own profile. The default report names the kind of evidence ("Your profile, Project") and leaves the words out. A checkbox adds quotes, cut to 300 characters, and the screen says to keep the file private if it is added. The domain drops quotes whatever the loader supplied unless the flag is on.

**Made by the worker, held in private storage.** Same shape as the resume PDF: a row (`report_exports`), a run, a task (`build_report`), a server-made storage key. A task for a deleted report does nothing. A file that cannot be written is a result (the row says failed, the task completes). A storage error retries and shows on the last attempt. No job text is logged or put in an error.

**Only the owner, only while ready and unexpired.** Download is an authenticated route, not a public link: someone else's report, an expired one and one still being made are all "not found". Responses are `attachment`, `no-store`, `nosniff`. Short-lived signed links need object storage and arrive with deployment (3.7).

**Limits that fit the cost.** Exporting is free and never counted against a plan (ADR-0051: reading and exporting what you have are never counted). Instead: at most 3 reports being made at once, 20 asks an hour, the newest 20 kept, and each expires after `REPORT_RETENTION_DAYS` (7). Expired and surplus reports are removed, and their files deleted, whenever the list is read or a report is asked for.

**Audit holds the action, never the filters or the text.**

## Alternatives considered
- **A document library (openpyxl, python-docx) in the product.** Rejected: two more packages in the supply chain for files this simple, and the reader we already trust is hand-written for the same reason. Kept as test-only tools.
- **Build the file in the request.** Rejected for consistency and for later size: the pattern (row, run, task, storage) already exists and gives retry, a visible state and admin visibility.
- **A report PDF.** Deferred (carryover). The resume PDF exists; a report PDF needs a template and the native PDF engine, which is not available outside the image.
- **Export from the browser.** Rejected by the requirements: reports come from stored data, not the screen.
- **Evidence quotes on by default.** Rejected (requirements 4: no full evidence text unless the person selects it).
- **A public signed link.** Deferred to object storage (3.7).

## Consequences
- A person can leave the product with their jobs and why each fits, in a form they can sort or edit.
- Compensation is not a column because it is not extracted from postings yet (carryover).
- Expiry is enforced on read, not by a timer. A report nobody lists stays in storage until the person next opens their reports or deletes the account (carryover with account deletion, T20).
- A file's text can still contain something a reader dislikes (a posting's own words). It cannot contain a formula.

## Evidence
Unit tests (42): neutralizing every formula start, XML-forbidden characters, long cells, the counts sentence, sources, criteria in words, the same data giving the same bytes, quotes left out, and CSV, XLSX and DOCX each read back with real readers (headers, rows, frozen pane, no formula cells, no macros or external references, odd characters, 100 jobs, no jobs). Integration tests (22) with the real database, API and worker: build, store privately, download, all three formats, quotes off and on, filters in words and junk filters dropped, formula strings planted in a job and neutralized end to end, another person gets 404 on read, download and delete, a worker for another owner does nothing, CSRF and sign-in, Row Level Security forced, retry then failed then asked again, a file that cannot be written fails without leaking text, three at once, rate policy, newest twenty kept, expiry removes the row and the file, delete removes the file and a late task does nothing, audit without text, exporting not counted. Browser tests (12) with axe in light and dark and a phone.
