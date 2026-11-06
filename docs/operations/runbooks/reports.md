# Runbook: reports (CSV, Excel, Word)

## A person says "The report could not be made"
The row is `failed` with a code. Look at the run in Admin (workflow "Building a report") and its steps (gather_jobs, write_file, store_file).
- `BUILD_FAILED`: the file could not be written. Reproduce with the person's filters in a test (build the report from a stub of the same jobs). Never copy their job text into a ticket.
- `STORAGE_FAILED`: private storage refused the file after three tries. Check disk space and permissions on `FILE_STORAGE_DIR` (or the bucket after 3.7). The person can press Try again once it is fixed.
A database error while gathering is retried by the worker. If every try fails the task dead-letters in Admin and the report stays "Being made" until the person deletes it.

## A report stays "Being made"
The worker is not running or is behind. Check `docker compose ps` and the task list in Admin (`build_report`). Only three reports can be made at once per person, so a stuck one blocks new ones with "Your other reports are still being made". The person can delete a report that is still being made, which cancels its task and frees the slot. If the worker is down, start it and the task completes.

## A spreadsheet shows a leading apostrophe
By design. A cell that began with `=`, `+`, `-` or `@` gets an apostrophe so no spreadsheet runs it as a formula. It is the posting's own text that began that way.

## The file will not open
Every format is tested with openpyxl, python-docx and the csv module, but real Excel and Word are a carryover (C-134). Keep the file (not its contents), note the application and version, and add a test that reproduces the structure problem. The writers are in `pv_files.report_formats`.

## A person wants evidence quotes
Make the report again with "Include short evidence quotes". Quotes are cut to 300 characters. The default leaves them out on purpose.

## A report is gone
Reports are deleted after `REPORT_RETENTION_DAYS` (7) and only the newest 20 are kept. Expired and surplus reports are removed when the list is read or a new report is asked for. Nothing can restore a deleted report. Ask for a new one.

## Settings
- `REPORT_RETENTION_DAYS` (default 7): how long a finished report can be downloaded.
- Rate limit `report_export_user` (20 an hour) and `report_download_user` (120 an hour).

## What to look at
- Table `report_exports` is tenant data with Row Level Security. Never query it without a tenant.
- Task type `build_report` and workflow type `report_export`.
- Audit events `report.requested` and `report.deleted` (action only, never the filters or text).
