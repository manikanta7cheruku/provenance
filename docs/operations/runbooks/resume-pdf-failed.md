# Runbook: A resume PDF cannot be made

A person presses "Make a PDF" and sees "The PDF could not be made. Your resume is safe. Try again.", or the button stays on "Making your PDF". The resume itself is safe: it is saved before the export starts.

## Detection
- The PDF panel in the studio.
- Admin, Runs: `resume_export` runs that failed, retried or have been running long.
- `resume_exports.status` and `error_code` for the person's resume (ids only, never content).

## Diagnosis
| Sign | Meaning | Action |
|---|---|---|
| Failed with `RENDER_FAILED` | The PDF engine raised for this content. The document passed validation, so suspect the engine or its libraries | `.\scripts\pv.ps1 logs worker`, look for the render step. Run `.\scripts\pv.ps1 pdftest` to confirm the engine works in the image |
| Failed with `STORAGE_FAILED` | The file store could not be written on every attempt | Check the files volume (space, permissions). `docker compose exec worker df -h /data/files` |
| Stays on "Making your PDF" | The task is queued, retrying, or the worker is down | `.\scripts\pv.ps1 queue`, then [worker failure](worker-failure.md) or [stuck task](stuck-task.md) |
| PDF text is in a plain system font | The shipped fonts did not load. Look for the warning "Font-face cannot be loaded" in the worker log | Rebuild the image (`.\scripts\pv.ps1 up`), check that `packages/files/src/pv_files/assets/fonts` has eight `.woff` files, and run `pdftest`, whose font test fails in this case |
| Messages "Fontconfig error: No writable cache directories" | The image has no writable cache folder | Rebuild. The Dockerfile creates `/tmp/cache` and sets `XDG_CACHE_HOME` |
| "The free plan keeps one resume" | Not a failure: the limit is a setting | `STUDIO_MAX_RESUMES` |

## Mitigation
The resume and its earlier versions stay editable and previewable, because the preview does not need the PDF engine. Tell people the PDF is delayed.

## Recovery
After fixing the cause, the person presses "Make a PDF" again. A failed export can be left alone: only the newest five are kept. Do not edit `resume_exports` by hand.

## Prevention
Run `.\scripts\pv.ps1 pdftest` after any change to fonts, the Dockerfile, WeasyPrint or the renderer. CI runs the same tests. Never paste resume text into tickets: use the resume id.
