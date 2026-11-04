# ADR-0043: Pictures and icons on the resume

Status: Accepted (checkpoint 2.11).

## Context
The owner asked for images, photos and icons after testing the canvas editor (ADR-0035). They are a real part of how people make a resume look finished, and a gap against other builders. They also bring the first file the product keeps that it cannot read as text, and the first thing in a resume that is not words. That raises four risks. An uploaded picture is untrusted input to a decoder, which is a large library fed hostile bytes. A photo carries hidden data (camera, place, time) the person did not mean to share. A picture is a way for one person's resume to reach another person's file. And a picture is information a screen reader, a PDF reader and a hiring system may not see.

## Decision

**One narrow door for decoding** (`pv_files.images.process_image`). The kind comes from the first bytes only (JPEG, PNG or WebP). Everything else is refused by name so the person is told why: SVG (it can carry script and links), GIF, HEIC, AVIF, BMP, TIFF, and files that are not pictures. The size is read from the header and a picture over 24 megapixels or 12,000 pixels on a side is refused **before any pixel is decoded**, because a small file can claim to be enormous. A large JPEG is decoded at a reduced size. An animated picture is refused. Every decoder warning or error is a refusal ("damaged picture"), never something to continue past. A file whose parts disagree with its type is refused.

**What is stored is never what was uploaded.** The picture is turned the right way up from its orientation tag, drawn again as a new JPEG (photos) or PNG (pictures with transparency, or only a few flat colors, such as a logo), cut down to 1,600 pixels on the longest side, with **no metadata at all**: no camera, place or time (EXIF), no comment, no color profile, no text chunk. Anything hidden after the picture or inside a tag is gone. The tests that check this found two real leaks in the first version of the code (a color profile and a JPEG comment survived), which is why they exist. The stored bytes are hashed, so the same picture uploaded twice is one row.

**Private storage, served only to the owner.** The row (`resume_images`, Row Level Security, migration 0016) says what the picture is, and the bytes live in private storage under a server-made key. The file is served only to its owner, with a type the server chose, `nosniff`, a `sandbox` content security policy and a private cache. Limits per person: 20 pictures and 12 MB. A resume may hold 5.

**A document can only use its owner's pictures.** A canvas refers to a picture by id. Every save and preview checks each id against the person's own pictures (`validate_canvas(raw, images)`), and a picture that is someone else's or was deleted is refused in the **same words**, so ids cannot be probed. With nothing to check against, a picture is never trusted. The PDF task loads only the owner's pictures and a document that refers to any other fails to render.

**Pictures are drawn into the page, not fetched.** The page that becomes a PDF (and the preview) embeds each picture as a data address, so rendering never requests anything and a PDF cannot refer to an outside address. The `alt` text is escaped. A picture that is missing draws an empty box and not an error.

**A picture in use cannot be deleted**, and "in use" includes saved versions of a resume, so restoring an old version can never point at a picture that is gone. Deleting the resume deletes its versions, and then the picture can go. This means a picture that was ever in a saved version stays until that resume is deleted. Purging old versions is carryover.

**Icons are data, not files.** Sixteen outline icons are lists of simple shapes on a 24 by 24 grid (`pv_domain.resume_icons`), drawn as an inline SVG that takes its color from the text color. Nothing is uploaded, nothing is stored as markup, and the markup the server writes is built only from this table. The browser draws the same shapes from `icons.ts`, and a golden file checks every icon at every weight on both sides. Brand logos are left out on purpose: they are trademarks and they change.

**Accessible and honest.** A picture has a description (alt text) the person writes, or is marked decorative. The editor says when a picture has none, the layout check says so as a note, and the PDF carries the description. An icon is decoration and is hidden from assistive technology unless the person gives it a label. The layout check says plainly that many employers advise against photos and some hiring systems ignore pictures, so nothing a reader needs should be only in a picture. ATS-safe templates stay text only. Pictures and icons add no text and do not change reading order.

## Alternatives considered
- **Accept SVG.** Rejected: it is markup that can run script and load addresses. Logos can be uploaded as PNG.
- **Store the upload and strip metadata later, or on read.** Rejected: the original would then exist on disk. Drawing it again before storing means the dangerous bytes are never kept.
- **A metadata-stripping library on the original bytes.** Rejected: it trusts a parser to find every kind of hidden data. Drawing the pixels again keeps only pixels.
- **Link pictures from a web address or a CDN.** Rejected: a request per render, a privacy leak, and a way to make the PDF task fetch anything.
- **Decode in a separate process now.** Deferred to deployment (carryover C-95). The decoder runs in the API process, behind the size and pixel limits.
- **Let a deleted picture leave an empty box in old versions.** Rejected: silently broken history. A picture in a saved version is kept instead.

## Consequences
- The decoder is a third-party library handling hostile input in the API process. Its limits and the refusals above reduce the risk, they do not remove it. Sandboxing is carryover.
- Photos are re-encoded as JPEG at quality 85, so a lossless original is not kept. That is the intended trade.
- A person cannot reorder, crop by dragging or rotate a picture in this checkpoint (crop is two position numbers).
- Pictures are not yet used by any template. They are added by hand.

## Evidence
Unit tests: 35 cases for uploads (kind from bytes, every refused type with its reason, an empty and an oversized file, the picture drawn again as JPEG or PNG, transparency and flat graphics, large pictures cut down, orientation, camera place and time gone, text chunks and profiles gone, a hidden script or archive after the picture gone, a header that claims a huge size, small, animated, damaged, a broken checksum and deterministic output); 29 for the canvas (ownership with the same words for stranger and deleted, bad ids, fit and shape and crop, alt text, page edges, the picture limit, every icon valid and plain, drawing from data addresses with escaped alt text, decorative and labelled icons, reading order and text unchanged); the golden CSS and icon files checked by Python and by the browser tests. Integration tests with the real database: security and checks, a stored file that is not the upload, kind from bytes, a safe name, metadata never served, duplicates, refusals with their sentences and nothing kept, the limits, serving only to the owner with the right headers, Row Level Security, use in a resume, another person's picture refused, the preview and the PDF task drawing pictures, the PDF task refusing a picture that is not the owner's, deleting (and not while used, including in a version), and the audit trail without the picture. Browser tests with accessibility checks in both themes for the dialogs, a selected picture and a selected icon.
