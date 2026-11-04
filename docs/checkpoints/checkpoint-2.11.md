# Checkpoint 2.11: Pictures and icons on the resume

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.11-images-and-icons`. Decision: [ADR-0043](../adr/0043-pictures-and-icons-on-the-resume.md). Runbook: [resume pictures](../operations/runbooks/resume-pictures.md). Builds on the canvas editor ([2.2](checkpoint-2.2.md)) and the templates ([2.3](checkpoint-2.3.md)).

## What this checkpoint is for
A finished resume often has a photo, a logo or small icons beside the contact lines. The owner asked for them after testing the canvas. They need care: an uploaded picture is untrusted, a photo hides data, a picture must not reach another person's file, and a picture is invisible to a screen reader and some hiring systems. This checkpoint adds pictures and icons and makes each of those safe and honest.

## 1. Build

**Upload.** Add picture, Upload a picture. JPEG, PNG or WebP up to 5 MB. The kind comes from the first bytes. SVG, GIF, HEIC and others are refused with the reason. A picture over 24 megapixels is refused without being decoded. Animated and damaged pictures are refused. What is kept is a fresh JPEG or PNG with no metadata (no camera, place or time), cut down to 1,600 pixels. 20 pictures and 12 MB per person.

**Pictures on the page.** Add to page puts a picture box on the canvas, shaped like the picture. Properties: a description (or decorative), shape (rectangle, rounded, circle), fit (fill and crop, or show whole), crop position, outline. Resizable by its handles, movable, groupable, lockable like any element. At most 5 pictures in a resume.

**Icons.** Add icon: 16 outline icons (email, phone, place, website, link, date, work, education, code, award, person, star, check, arrow, company, message). Choose the icon, the line weight, the color (from the style) and the size. A label for screen readers is optional: without one the icon is skipped.

**Safe and accessible.** A picture belongs to its owner and can only be used in the owner's resumes. It is drawn into the page and the PDF from its own bytes. A picture in use, including in a saved version, cannot be deleted. The layout check says plainly what pictures risk and asks for a description. Pictures and icons add no text and do not change the reading order. ATS-safe templates stay text only.

**Data.** Migration 0016: `resume_images` (Row Level Security, forced). Routes: `GET|POST /studio/images`, `GET /studio/images/{id}/file`, `DELETE /studio/images/{id}`. A shared loader (`pv_files.pictures`) gives the API and the worker the same owner-only pictures. Pillow is now a declared dependency.

## 2. UX

- Every refusal says what is wrong and what to choose instead, in plain words.
- The dialog says what is removed from a photo and that photos are not for everyone.
- A picture with no description is flagged in the properties and in the layout check, with the fix.
- A picture that cannot be deleted says why and what to do.

## 3. Technical acceptance criteria

1. The type of an upload is decided from its first bytes. SVG and every other type except JPEG, PNG and WebP are refused by name.
2. A picture over the pixel or size limit is refused before it is decoded. Animated, damaged and tiny pictures are refused. Every decoder warning is a refusal.
3. What is stored has no metadata: no camera, place or time, no comment, no profile, no text chunk, nothing after the picture. The same upload always gives the same stored bytes.
4. A picture is served only to its owner, with the type the server chose, `nosniff`, a sandbox policy and a private cache. Another person gets 404.
5. A document can only use its owner's pictures. A stranger's and a deleted picture are refused in the same words, and with nothing to check against a picture is never trusted. The PDF task never draws a picture that is not the owner's.
6. Pictures are embedded as data addresses. Nothing is fetched. The description is escaped.
7. A picture in use, including in a saved version, cannot be deleted.
8. Icons are drawn only from the fixed table. The browser and the server draw every icon identically.
9. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the canvas with the picture dialog (empty and with pictures), a picture selected (with and without a description), the icon dialog and an icon selected, in light and dark. The dialogs are native dialogs with focus handling. Each picture and icon button names what it acts on. A picture has a description or is marked decorative. An icon without a label is hidden from assistive technology.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_image_processing.py` | uploads: kinds, refusals, what is kept and thrown away, hostile files |
| `tests/unit/test_canvas_pictures.py` | picture and icon validation, ownership, drawing |
| `tests/unit/test_resume_canvas.py` | golden CSS and icon files |
| `tests/integration/test_resume_images.py` | the database: upload, serving, use in a resume, the PDF, deleting, privacy |
| `src/features/studio/canvas/pictures.test.ts` | the same drawing as the server, making pictures and icons, the layout check |
| `e2e/pictures.spec.ts` | the dialogs, upload and refusal, properties, icons, layers, the limit, axe in both themes |

## 6. Commit

```
feat(studio): add pictures and icons to the canvas
```

## 7. Interview defense

- Why a decoder is dangerous, and what each limit and refusal is for (type from bytes, size before decoding, animated, warnings as errors).
- Why the picture is drawn again instead of having its metadata removed, and how the tests found two real leaks.
- Why an id that is not the person's gets the same sentence as one that was deleted.
- Why pictures are embedded as data addresses.
- Why SVG is refused, and why icons are data.
- Why a picture in a saved version cannot be deleted.
- What was not proven: decoding in a separate process, a real photo from a real phone, a PDF with a picture opened in a real reader.

## 8. Verified and not verified

Verified: all tests above with the real database. Hostile files made with Pillow in the tests. The preview and the PDF task drawing pictures (the PDF engine itself is stood in for in these tests).

Not verified: a real PDF with a picture opened in a PDF reader and a hiring system (the PDF tests need Docker, see below), photos from real phones (orientation, color profiles, HEIC), decoding in a separate process (carryover C-95), and screen reader behaviour of the dialogs and properties.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
This runs migration 0016. Open the studio, choose Add picture, upload a photo from your phone (try a HEIC one too and read the message), add it, describe it, make it a circle, then export the PDF and open it. Add an icon next to your email.
