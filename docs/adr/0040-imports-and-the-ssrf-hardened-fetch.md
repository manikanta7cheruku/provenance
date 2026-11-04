# ADR-0040: Imports (typed, spreadsheet, web page) and the hardened fetch of an address a person typed

Status: Accepted (checkpoint 2.8).

## Context
Until now a job reached the product by one route: the person pasted text. Real use needs more: a job typed in by hand, a list of jobs from a spreadsheet, and "read this page for me". Each one brings a new kind of untrusted input.

- A **spreadsheet** is a file written by someone else. It can be a zip bomb, carry a macro, name an external entity, hold a formula, or simply be huge.
- A **web address** typed by a person is the most dangerous input the product has taken so far. If the server requests it, the person chooses where our machine connects. An address that points at our own network, a cloud metadata service or a database turns the server into a tool against the place it runs in (server side request forgery, SSRF).
- Whatever a **web page** says is untrusted text, including text that tries to give the product instructions.

## Decision

**Every way in ends at the same place.** Typed, spreadsheet and web page jobs become the same private posting a paste does (one function, `store_draft`), are read by the same extraction step and are protected by the same Row Level Security. The `acquisition_method` records how the text arrived (`manual_entry`, `csv_import`, `xlsx_import`, `url_import`), so the product never claims to have searched anything.

**The API never opens a file and never requests an address.** It checks the first bytes of the file (or the address with the pure rules below), stores the file in private storage and queues a task. The worker does the reading. A person therefore cannot make the API server connect anywhere, and the worker is the only code with network access for this feature.

**Spreadsheets (`pv_files.tabular`).** The kind comes from the first bytes, never from the name or the type the browser claims. CSV is decoded (UTF-8, UTF-16, then Windows text) and split by the standard library with a field size limit. XLSX is read from its zip and XML with the standard library and defusedxml, with every limit ours: entry count, total uncompressed size, per-entry compression ratio, no path that climbs out, a per-part read cap that stops an archive that lies about its size, no external entities or DTDs, encrypted entries refused, and a workbook that carries a macro project refused without being opened. A cell gives its stored text or number only: **a formula is never calculated** and an external link is never followed. Rows, columns, cell length and file size are capped (200 jobs, 40 columns, 5 MB).

**Rows (`pv_domain.job_import`).** Headers are matched by meaning ("Job title", "Position" and "Role" all mean title). One column, the description, is required. Each row is checked on its own and ends as created, already saved, or rejected with a short code and a sentence. One bad row never stops the others. A row repeated in the file is kept once. A cell that starts with `=`, `+`, `-` or `@` is stored as the text it is, and the product never writes a spreadsheet back, so it cannot run.

**The report.** `import_batches` and `import_items` (Row Level Security, forced) hold one row per spreadsheet row or page, with the reason in words and the posting it made. The report never holds posting text. Deleting a posting leaves the report, with its link cleared. The uploaded file is deleted from storage when the import ends, whatever the result.

**Web addresses, in three layers.**
1. *The rules* (`pv_domain.url_safety`, pure). https only, the standard port only, no user name in the address, no address written as numbers in any form (dotted, decimal, hex, octal, bracketed IPv6), no name that cannot exist on the public internet (`localhost`, single labels, `.local`, `.internal` and similar), and no site that forbids automated reading (LinkedIn, Indeed, Wellfound and others: the answer is "paste the description instead"). Every refusal has a code and a sentence.
2. *The resolution* (`pv_worker.safe_fetch`). The name is resolved **once**. Every address in the answer must be public (private, loopback, link local including `169.254.169.254`, carrier grade NAT, multicast, reserved, translation and tunnel prefixes, and an IPv4 address inside an IPv6 one are all refused). One bad address among good ones refuses the name.
3. *The connection*. The request goes to the **address that was checked**, not to the name, with the name still sent for the certificate check and the Host header. A name that answers differently the second time (DNS rebinding) cannot change where the connection goes.

Redirects are followed by hand, at most three, and **every hop goes through all three layers again**: a redirect into a private network, to a forbidden site or to another port is refused. The answer must be a web page (HTML or text), is read as it arrives and stopped at 2 MB (a compressed answer is counted after it is expanded), has a total deadline, and no cookie or credential is ever sent or kept. A page that cannot be read is a **result** with a sentence and, where useful, advice to paste instead. Trouble that may pass (the site is busy) is retried and becomes a visible result on the last attempt.

**What is read from a page.** Structured job data that many career pages publish (JSON-LD `JobPosting`) first, then the visible text. Scripts, styles, navigation and footers are dropped. The text is stored as the posting and read like a paste. **An instruction inside a page is only text**: it is stored as the posting's own words and the reading step treats it as data, as it does for every posting.

**Limits per person** (rate limits): 10 file imports, 30 address imports and 60 typed jobs per hour.

## Alternatives considered
- **Fetch the address in the API.** Rejected: it would make the API server the thing a person can aim. The worker is the one place that does it, with its own checks.
- **Check the address, then let the HTTP client resolve and connect.** Rejected: the check and the connection would resolve the name separately, which is exactly the gap DNS rebinding uses. Connecting to the checked address closes it.
- **A block list of bad addresses only.** Rejected: lists miss encodings. The rules accept a small safe set (a public name over https) and refuse the rest.
- **A spreadsheet library (openpyxl, pandas).** Rejected: more code that opens untrusted files with limits we do not control. The minimal reader reads only the first sheet's text and numbers.
- **Run the whole import in the request.** Rejected: 200 rows and a slow web page do not belong in a request, and a worker task survives the person leaving the page.
- **Obey robots.txt for a person's own link.** Not done. This is one page a person chose to read, not a crawl, and the number of requests per person is limited. Recorded as carryover.

## Consequences
- Pages that need a script to show their text, or that need a sign-in, give no text and are rejected with advice to paste. That is honest, and common for modern career sites.
- The SSRF defence has been proven against a fake name server and a fake web server. It has not been tried from the real hosting network, where the network's own rules (no route to private ranges from the worker) are the third layer (carryover).
- A spreadsheet row becomes one reading task. 200 rows is 200 model calls the first time, which is a cost to watch once a real model is set up (carryover).
- Only the first sheet of a workbook is read.

## Evidence
Unit tests: the address rules (about 90 cases covering every encoding of a private address, credentials, ports, schemes, look-alike names), private and special network ranges, the safe fetch against a fake name server and web server (pinning, rebinding, mixed answers, redirects into private places, size, compression bomb, content types, status codes, deadline, cookies), the spreadsheet readers (zip bomb, traversal, macros, encrypted, entity expansion, formulas, huge cells and rows), row rules and page reading. Integration tests with the real database: typed entries, CSV and XLSX imports with a report, duplicates, a missing file, refused uploads, address refusals, a page becoming a posting, pages that cannot be read, retry then result, privacy between people, Row Level Security, the audit trail with no content. Browser tests with accessibility checks in light and dark.
