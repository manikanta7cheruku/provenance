# Export and Reporting Requirements

Status: Decided (Phase 0). Implemented in Phase 3, checkpoint 3.4.

## 1. Principles

- Generated server-side from structured result data. Never from screenshots of the UI.
- Reproducible: the same stored run produces the same report content.
- Every export states when the search was performed, because postings change.
- Exports are user scoped, authorized, rate limited, and written to private storage with short-lived signed links.

## 2. Formats

| Format | Use | Notes |
|---|---|---|
| CSV | Spreadsheet import and analysis | UTF-8 with BOM option for Excel. Formula injection prevention: cells beginning with = + - @ are prefixed with an apostrophe |
| XLSX | Sortable workbook | Sheets: Summary, Opportunities, Requirements, Evidence. Same injection protection |
| PDF | Shareable report | Generated from a template |
| DOCX | Editable report | Generated from structured data |

## 3. Contents

Search criteria, timestamp, sources searched, sources user-imported, jobs discovered, count after dedup, ranked opportunities, and per opportunity: company, role, location, source, acquisition method, original posting link, compensation, eligibility, requirement coverage, evidence summary, recommendation with reasons, generated materials status.

Summary footer example: "41 opportunities found. 12 strong matches. 18 possible matches. 11 rejected by eligibility rules." Counts come from stored data.

## 4. Controls

| Control | Rule |
|---|---|
| Authorization | Only the owner can generate or download |
| Quota | Counts against export units if configured. Cheap relative to LLM work |
| Retention | Exports expire and are deleted on schedule and on account deletion |
| Privacy | No evidence full text unless the user selects it. Default is evidence summaries and links |
| Failure | Generation failure is retried. User sees a clear state and can retry |

## 5. Acceptance criteria

1. A report generated from a run contains the timestamp and sources searched.
2. Formula-injection test strings are neutralized in CSV and XLSX.
3. Another user's export link returns 404.
4. PDF and DOCX open without errors in standard viewers.
