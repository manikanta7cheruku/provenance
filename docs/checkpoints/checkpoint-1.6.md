# Checkpoint 1.6: Resume upload, parsing in the worker, editable profile and preferences

Phase 1, Foundation and Core Intelligence. Branch `phase-1/checkpoint-1.6-resume-profile`. Decisions: [ADR-0029](../adr/0029-resume-storage-parsing-and-profile-entries.md). Runbook: [resume parsing fails](../operations/runbooks/resume-parse-failed.md).

Roadmap revision 2 moved evidence chunks and hybrid retrieval to checkpoint 1.7. This checkpoint builds the profile they will index.

## 1. Build

**Database (migration 0004, literal SQL).** `resumes` (metadata only, one per user, generated storage key, parse and review status, parse generation, counts, short error code), `profile_preferences` (typed columns, one row per user), and `profile_entries` gains `source`, `source_resume_id`, `source_key` and `position`. Both new tables use the same forced Row Level Security policy as `profile_entries`.

**Files (`pv_files`, new package).** `FileStorage` interface with `LocalDiskStorage` (server-generated keys only, atomic writes, mode 0600, no public URL). `extract_text` reads PDF (pypdf: encryption, page and character caps) and DOCX (standard library plus defusedxml: entry count, total size and ratio limits, hard byte cap on the XML, no external entities, no path traversal names). `check_upload` decides the type from the first bytes.

**Domain (`pv_domain`).** `resume.py`: limits, file type detection, safe display names, error codes with user-facing sentences, `resume_ui_state`. `profile.py`: field specs for eight entry types, strict and lenient validation, recommended-field flags, grounding (`is_grounded`), identity keys for duplicates, and the specs in a JSON form for the browser. `ResumeUiState` joins the shared state vocabulary.

**Model step (`pv_llm`).** `build_provider` (the one place settings become a provider), `generate_structured` (JSON matched to a Pydantic schema, one retry whose feedback names field paths and error kinds and never quotes values), `parse_resume_text` (versioned prompt `resume-parse-1`, the resume wrapped as data in markers it cannot contain, then validation and grounding in code).

**Worker (`parse_resume`).** Steps: read file, extract text, structure profile, save profile, each recorded in the run with counts and timings. Every model call goes to `llm_calls` with the prompt version and a content hash. Visible failures (unreadable file, model gave nothing usable, AI not configured, file missing) are results: the resume is marked failed with a short code and the task completes. Only transient trouble is retried. A task for a deleted resume or an older generation does nothing. Saving replaces only entries a parse created that the person never edited.

**API.** `GET /resume`, `POST /resume` (raw body, `X-Filename`), `GET /resume/file` (owner only, attachment, no-store), `DELETE /resume`, `POST /resume/reparse`, `POST /resume/confirm`. `GET /profile/schema`, entries validated against the specs with per-field messages, `GET` and `PUT /profile/preferences`. Upload and re-read are rate limited. The body limit allows the 5 MB upload only on the upload route.

**Web (`/profile`).** Resume section (idle, uploading, uploaded, reading with polling, ready to review, needs correction, confirmed, failed with retry, download, read again, delete with confirmation), entries grouped by type with provenance ("From your resume" or "Added or edited by you"), missing details marked, inline edit and add forms drawn from the server's specs, remove with confirmation, and a preferences form. `useAsync` now tracks "loaded" separately so a legitimate `null` is not "loading".

**Compose.** A named volume `files` at `/data/files`, shared by the `api` and `worker` containers (`FILE_STORAGE_DIR`). The image creates the folder owned by the app user.

## 2. UX

- A student uploads once, sees what is happening in plain words, and can leave the page while it is read.
- Every entry says where it came from. Anything the reader suggested that is not in the resume is left out, and the user is told how many.
- Missing details are marked on the entry, and "Confirm anyway" exists so advice never blocks.
- A failure says what happened, that the file is safe, and what to do next. With no AI key it says the reading service is not set up yet.
- Deleting the file keeps the entries, and the dialog says so.

## 3. Technical acceptance criteria

1. Migration 0004 applies on top of 0003 and the down migration reverses it. `resumes` and `profile_preferences` are invisible to other tenants and with no tenant set (raw SQL test). One resume per user is enforced by the database.
2. The type comes from the first bytes. A renamed file is accepted or refused by content, never by name or Content-Type. Empty, over 5 MB, non-PDF, non-DOCX and fake ZIP files are refused with specific codes and nothing is stored.
3. A decompression bomb, too many archive entries, traversal member names, external XML entities and an entity expansion attack are refused.
4. Page and character caps, encrypted PDFs and image-only files produce short error codes with plain messages.
5. Storage keys cannot leave the storage folder. Keys are random and never contain the file name.
6. Only the owner can download. Another user gets 404. The download is an attachment with `no-store`.
7. Parsing keeps only entries that are valid and grounded. Invented employers are dropped and counted. Unknown fields never reach the database. A hostile resume cannot close the data block it is wrapped in.
8. The model is called once, with one guided retry. The retry prompt contains no value from the first answer. Both calls are recorded in `llm_calls`.
9. Running the same task twice, running a task for a replaced generation, and running it for a deleted resume are safe.
10. A re-parse replaces only untouched parsed entries and never duplicates an edited one.
11. Visible failures end the run as failed and complete the task. A busy provider is retried and fails visibly on the last attempt.
12. Delete removes the file and the row, cancels a queued parse, keeps the entries, and is audited without the file name.
13. Ruff, mypy, import-linter, unit tests, integration tests and the web checks pass. CI is green.

## 4. UX acceptance criteria

1. A user without a resume sees an upload with its limits and an alternative (add by hand).
2. While reading, a status line explains what is happening and the page updates by itself.
3. Each entry shows its source and what is missing, and can be edited, removed or added with field-level messages.
4. "Needs correction" clears as the user fixes entries. "Confirm anyway" is always available.
5. The preferences form saves with a polite confirmation and explains why the answers matter.

## 5. Accessibility acceptance criteria

1. Axe finds no WCAG 2.2 A or AA violation on the profile screen in no resume, reading, needs correction, confirmed and failed states, with an edit form, an add form and the delete dialog open, in light and dark.
2. Forms have visible labels, hints and errors linked to their fields. The first invalid field receives focus on submit. Escape cancels an inline form.
3. Status text is announced politely. Errors use `role="alert"`.
4. The upload keeps the native file input, so it works with a keyboard and a screen reader.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_profile_domain.py` | validation (strict and lenient), grounding, keys, file rules, state mapping |
| `tests/unit/test_files.py` | storage key safety, PDF and DOCX extraction, bombs, entities, traversal |
| `tests/unit/test_resume_parse.py` | structured retry (no value echoed), grounding, injection limits, data block markers |
| `tests/integration/test_resume_profile.py` | upload, refusal cases, download, delete, isolation, worker step, idempotency, re-parse, failures, confirm, entries, preferences |
| `src/features/profile/profile.test.tsx` | describe helpers, entry form, resume section states |
| `e2e/profile.spec.ts` | axe on every profile state in both themes, and the whole journey in a browser |
| `scripts/check-states.mjs` | now also compares `ResumeUiState` with `RESUME_UI_STATES` |

Test helpers `tests/documents.py` build valid PDF and DOCX files with no extra libraries. The earlier tenant test that created an empty skill now supplies a name, because entries are validated.

## 7. Document

[ADR-0029](../adr/0029-resume-storage-parsing-and-profile-entries.md), [data-model.md](../architecture/data-model.md), [security-controls.md](../security/security-controls.md) and [threat-model.md](../security/threat-model.md) (T7), [ux-specification.md](../product/ux-specification.md), [operator-commands.md](../operations/operator-commands.md), [llm-provider-gemini.md](../operations/llm-provider-gemini.md), the [resume parsing runbook](../operations/runbooks/resume-parse-failed.md) and the runbook index.

## 8. Commit

```
feat(profile): add resume upload, parsing in the worker, editable profile and preferences
```
Include the updated `uv.lock` (new workspace package `pv-files`, dependencies `pypdf` and `defusedxml`, dev dependency `types-defusedxml`) and `package-lock.json` is unchanged.

## 9. Interview defense

You should be able to explain:
- How an upload is validated (first bytes, size while streaming, archive limits, XML entity safety) and why a raw body beats multipart here.
- Why storage keys are server generated and what the `FileStorage` interface buys.
- How the model is kept honest: schema, one guided retry that never echoes values, validation, grounding. And the limit of grounding.
- Why a visible parse failure is a result and a busy provider is a retry.
- How generations and "replace only untouched entries" make the worker idempotent and keep the user's edits.
- Why UI states are derived, and how the frontend and backend lists are kept equal.
- The `null` is not "loading" bug and what it teaches.

## 10. What was verified and what was not

**Run in this checkpoint:** ruff, mypy (strict), import-linter; the Python unit tests (248 passed); the full integration suite against the real PostgreSQL in the Docker stack with the worker stopped (176 passed, 30 of them new); migration 0004 up, down and up again; the web checks (boundaries, states, tokens, contrast, copy, type check), 45 web unit tests, the production build and 47 browser tests in Edge. A live run against the Docker stack (real API, queue, worker and shared volume): upload, extraction by the worker, the "not set up" failure with its message, byte-identical download, duplicate upload refused, re-read, delete and an empty volume.

**Not verified:** a real model call (no API key is configured, so the model step is covered by a scripted stand-in and the real Gemini client by the mocked-transport tests from 1.4); scanned image resumes (not supported); Firefox, Safari, screen readers and touch devices; GitHub CI on the branch; behavior with a paid-tier model; very large PDFs on a slow machine (pypdf runs in the worker with page and character caps but no wall-clock timeout beyond the task lease).

Likeliest first-CI problems: the new package in `uv sync --frozen` if `uv.lock` is stale, `types-defusedxml` missing for mypy, and the `files` volume permissions in a fresh Docker environment.

## 11. Run it yourself

```powershell
.\scripts\pv.ps1 up
.\scripts\pv.ps1 invite you@example.com
```
Open http://localhost:5173, sign up, open Profile and upload a text PDF. With no `GEMINI_API_KEY` you will see the "reading service is not set up" message, which proves the file, the queue and the worker. To see real entries, put a key and a model in `.env` (`.\scripts\pv.ps1 ai-check` lists the names), run `.\scripts\pv.ps1 restart worker`, and press Read it again. Use only your own resume on a free tier.
