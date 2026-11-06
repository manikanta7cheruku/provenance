# Checkpoint 3.4: Server-side reports (CSV, Excel, Word)

Phase 3, Intelligence, Monetization and Production. Branch `phase-3/checkpoint-3.4-exports`. Decision: [ADR-0052](../adr/0052-server-side-reports.md). Requirements: [export-reporting-requirements.md](../product/export-reporting-requirements.md). Runbook: [Reports](../operations/runbooks/reports.md). Builds on the workbench ([2.8](checkpoint-2.8.md)), the evidence check ([1.9](checkpoint-1.9.md)) and the plans work ([3.3](checkpoint-3.3.md)). The resume PDF export already exists from [2.1](checkpoint-2.1.md).

## What this checkpoint is for
Let a person take their jobs, and why each one fits, out of the product, safely: made on the server from stored data, owned by them, expiring, and never able to carry a spreadsheet formula.

## 1. Build
- **Three formats** from one report model: CSV (UTF-8 with a byte order mark), an Excel workbook (Summary, Opportunities, Requirements, Evidence) and a Word document (summary, jobs table, job by job).
- **The list you are looking at**: a report holds the jobs the current filters choose, up to 500, and says how it was chosen.
- **Says when and from where**: made on (UTC), the filters in words, the sources and how each job came in, a counts sentence from stored data, and a note that postings change.
- **Safe cells**: no leading `=` `+` `-` `@`, no characters XML forbids, no formula ever written.
- **Evidence quotes off by default**, an option adds short ones.
- **Made by the worker**, stored privately, downloaded only by the owner while ready and unexpired.
- **Limits**: three being made at once, 20 asks an hour, the newest 20 kept, 7 days then deleted. Exporting is never counted against a plan.
- Data: migration 0021 (`report_exports`), routes under `/api/v1/reports`, a worker task `build_report`, `pv_domain.report`, `pv_files.report_formats`, and an Export panel on the jobs list.

## 2. UX
- A quiet "Export these jobs" disclosure under the list controls. It says what it does, that it is free and never sent anywhere.
- Being made, Ready (with size, job count, filters and a deletion date) and Could not be made (with Try again, which repeats the same format and filters) are written in words, not only in color.
- Deleting is one click and announced, and also frees a report that is stuck being made.
- An empty list cannot be exported and says why.

## 3. Technical acceptance criteria
1. A report contains when it was made and the sources the jobs came from, and the filters in words.
2. Formula test strings planted in a job are neutralized in CSV and XLSX, end to end.
3. Another person's report, download or delete returns 404.
4. CSV, XLSX and DOCX open with standard readers without error.
5. Evidence quotes are absent unless asked for.
6. An expired report cannot be downloaded and its file is deleted.
7. A file that cannot be built or stored becomes a visible failed state that can be asked for again, with no job text in any error or log.
8. Only three reports can be made at once and asks are rate limited.
9. Row Level Security is enabled and forced on `report_exports`.
10. Ruff, mypy, import-linter, unit tests, the integration tests for this checkpoint, and the web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation with a ready, a failed and a being-made report in the panel, in light and dark, and nothing scrolls sideways at 390 pixels. The panel works from the keyboard. Download and Delete have names that say which report. Changes are announced.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_report.py` | the rules and the three formats read back with real readers (42) |
| `tests/integration/test_reports.py` | the database, API and worker (22) |
| `e2e/reports.spec.ts` | the export panel, axe in both themes, a phone (12) |

## 6. Not verified
The files opened in the real Excel, Word, LibreOffice and Google Sheets (C-134). A report PDF (not built, C-135). A compensation column (not extracted, C-136). Expired files for people who never list their reports, and account deletion (C-137). A screen reader pass (C-138). Signed short-lived links (arrive with object storage, C-139). The full 28 minute backend suite was not run for this checkpoint by agreement. It runs after all checkpoints are built.

## 7. What is next
3.5, observability, the Run Inspector and the Admin Console.
