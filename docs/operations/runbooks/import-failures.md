# Runbook: Import failures

A spreadsheet or web address import ends in failure, rows are rejected, an import stays "Waiting to start", or an address that should be refused was accepted.

## Detection
- The import report page (`/opportunities/imports/:id`) and `GET /api/v1/imports/{id}`: status, counts, and a reason for every row.
- `audit_events` actions `import.file_started`, `import.url_started` and `job.entered` (kind, size and host only, never content).
- Tasks of type `import_file` and `import_url` in the task table (state, attempts).

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| Whole import "Could not be used", message about the description column | The header has no column named Description, Job description, Details, Posting or Text | Rename the column and import again |
| "more than 200 jobs" | File over the row limit | Split the file |
| "macros", "password protected", "packed in a way we do not read" | The file was refused on purpose | Save as plain XLSX or CSV. Do not relax the checks |
| Some rows "Not added" | Each row says why: description too short, link not a web address, title too long, repeated in the file | Fix those rows and import the file again. Rows already saved are reported as saved |
| Web page "private network" or "numbers" | The address rules or the resolved addresses were refused | Expected. Never relax this to make an address work |
| Web page "paste the description instead" | The site forbids automated reading, or answered 401, 403 or 429, or gave no text (the page builds its text with scripts) | Paste the description |
| Web page "site had a problem" after three tries | The site answered 5xx each time | Try again later |
| Import "Waiting to start" for a long time | The worker is not running or is not claiming `import_*` tasks | See the [worker runbook](worker-failure.md) and [stuck task runbook](stuck-task.md) |
| An address that should have been refused was accepted | A gap in the address rules or in the fetch | Treat as a security incident: stop the worker's outbound access if needed, add a failing test to `test_url_safety.py` or `test_safe_fetch.py`, then fix |

## Mitigation
Imports are independent of everything else. If the fetch layer misbehaves, stop the worker's `import_url` handling by removing it from the registry, or block the worker's outbound network, without affecting searching, pasting or the studio.

## Recovery
An import that failed can simply be done again: the same text never makes a second posting. The uploaded file is deleted when the import ends. A leftover file under `imports/` in private storage with no batch pointing at it is safe to delete.

## Prevention
Every new way a file or page can be wrong gets a test first. Keep the address rules a short list of what is allowed and not a long list of what is not. Check the network rules of the worker host at deployment (carryover).
