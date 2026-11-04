# Checkpoint 2.8: Imports (typed, spreadsheet, web page) and the hardened fetch

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.8-import`. Decision: [ADR-0040](../adr/0040-imports-and-the-ssrf-hardened-fetch.md). Runbook: [import failures](../operations/runbooks/import-failures.md). Builds on the job posting flow ([1.8](checkpoint-1.8.md)), the fetch layer ([2.6](checkpoint-2.6.md)) and duplicate detection ([2.7](checkpoint-2.7.md)).

## What this checkpoint is for
A person should be able to bring a job in the way that suits it: paste it, type it, point at a page, or bring a whole list from a spreadsheet. Each of those is untrusted input. A spreadsheet can be a bomb. A typed web address can aim our server at its own network. A web page can carry instructions. This checkpoint adds the three new ways in, makes each one safe, and tells the person exactly what happened to every row.

## 1. Build

**Add a job** (Opportunities). One choice of four: Paste text (as before), Type it in, From a link, From a spreadsheet. All end as the same private posting, read the same way. How it arrived is recorded and shown ("Typed in by you", "From your CSV file", "Read from a link you gave").

**Type it in.** Title, company, place, source label, optional link and what the job asks for. Fields become labelled lines in the posting text. The same words twice make one posting.

**Spreadsheet.** CSV or XLSX, up to 5 MB and 200 jobs. The first row names the columns, matched by meaning. A description column is required; title, company, location, link and source are used when present. Each row ends as added, already saved, or not added with a sentence. Unused columns are listed. Formulas are never calculated. Macros, passwords, zip tricks and entity tricks are refused.

**From a link.** One https page. The worker reads it with the hardened fetch: public names only, every resolved address checked, connection to the checked address, redirects checked again at every hop, size and time limits, no cookies. The page's structured job data is used first, then its visible text. A page with no readable text, or a site that forbids automated reading, gets a sentence and the advice to paste instead.

**The report.** `/opportunities/imports/:id` shows the state in words, the counts, every row, and links to the postings made. Recent imports are listed on the jobs page. The report never holds posting text and survives deleting a posting.

**Data.** Migration 0013: `import_batches`, `import_items` (Row Level Security, forced) and four new acquisition methods on postings. Worker tasks `import_file` and `import_url`. Routes `POST /jobs/manual`, `POST /imports/file`, `POST /imports/url`, `GET /imports`, `GET /imports/{id}`.

## 2. UX

- One choice, four forms, the same ending: the job is read and the person sees what it asks for.
- Every refusal says what is wrong and what to do ("copy the description and paste it instead").
- A failed or partly failed import never hides what worked. Rows that failed are listed with their reason so the file can be fixed and imported again; rows already saved are reported as saved, not duplicated.
- The person can leave while an import runs.

## 3. Technical acceptance criteria

1. Every address the rules refuse is refused before any name lookup or request. Every encoding of a private address is refused.
2. A name that resolves to a private address, or to a mix of public and private, is refused with no request made.
3. The connection goes to the address that was checked. A name that answers differently the second time does not change it.
4. A redirect into a private place, to another port, to http or to a forbidden site is refused, and the hop is never requested. At most three redirects.
5. The size limit stops an oversized, a lying and a compressed-bomb answer. Only web page types are accepted. No cookie or credential is sent or kept. The whole request has a deadline.
6. A zip bomb, a path that climbs out, too many entries, a lying entry size, an encrypted entry, a macro workbook and an entity expansion are refused. A formula is never calculated.
7. A bad row never stops the others. A row repeated in the file is kept once. A row already saved is reported as saved. Running the task twice makes no second copy.
8. The API opens no file and requests no address. Another person's import is 404. Imports are audited without content.
9. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the Add a job section in each of its four forms, the recent imports table and the report, in light and dark. State is written as words next to its dot. The file control is the native input. The report table is named and scrolls inside its own region.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_url_safety.py` | the address rules and every special network range |
| `tests/unit/test_safe_fetch.py` | pinning, rebinding, mixed answers, redirects, size, compression, types, statuses, deadline, cookies |
| `tests/unit/test_tabular.py` | CSV and XLSX readers and every hostile file |
| `tests/unit/test_job_import.py` | columns, rows, reports, formulas, limits |
| `tests/unit/test_job_page.py` | structured data, visible text, hostile markup |
| `tests/integration/test_imports.py` | the database: typed, CSV, XLSX, URL, privacy, Row Level Security, audit |
| `src/features/opportunities/imports.test.tsx` | the forms and the report |
| `e2e/imports.spec.ts` | the four ways, refusals, the report, axe in both themes |

## 6. Commit

```
feat(import): add typed, spreadsheet and web page imports with a hardened fetch
```

## 7. Interview defense

- Why the API never fetches and the worker does, and what the three layers of the address defence each stop.
- Why the connection goes to the checked address, and what DNS rebinding is.
- Why a minimal spreadsheet reader instead of a library, and what each limit is for.
- Why a formula is stored as text, and why that is safe here.
- Why a bad row does not stop the others, and why the report holds no posting text.
- What was not proven: the defence from the real hosting network, and a real career page.

## 8. Verified and not verified

Verified: all tests above with the real database, against a fake name server and a fake web server.

Not verified: reading a real career page from the real network (carryover), the network-level third layer in production (carryover), the cost of reading 200 rows with a real model (carryover), robots rules (carryover), and an import by a person on a phone.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0013. Open Opportunities, choose Add a job and try each way. Try a CSV with a Description column, a link to a public job page (not LinkedIn or Indeed) and a link to `https://localhost/`, which is refused in words.
