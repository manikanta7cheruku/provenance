# Runbook: Resume pictures

A picture will not upload, a picture is missing from a resume or a PDF, a picture cannot be deleted, storage is filling up, or a decoder problem is suspected.

## Detection
- The Pictures dialog in the studio: the list, the sizes, and the sentence for a refusal.
- `resume_images` (one row per picture), the files under `images/` in private storage, and `audit_events` actions `resume_image.uploaded` (the kind and the size only) and `resume_image.deleted`.
- API logs for a decoder error: an upload that is refused as damaged returns 422. An API process that dies while reading an upload is a decoder crash.

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| "This kind of picture is not accepted" | SVG, GIF, HEIC or another type | The person converts it to JPEG, PNG or WebP. Do not accept the type |
| "much larger than a resume needs" | Over 24 megapixels or 12,000 pixels a side | The person resizes it. Never raise the limit to make one work |
| "damaged or could not be read" | The decoder refused it, or it is truncated | Save it again from the original. If many good pictures are refused, check the Pillow version |
| "Animated pictures are not used" | An animated WebP or PNG | Use a still picture |
| 413 "too large" | Over 5 MB | A smaller picture |
| "You can keep up to 20 pictures" / "space allowed" | Limits per person | Delete pictures that are not used |
| A picture will not delete: "used in one of your resumes, or in a saved version" | The picture is in a document or in its history | Remove it from the resume, then delete that resume or accept that it stays. History keeps it so restoring never points at a missing file |
| A box is empty in the PDF | The picture row exists but its file is missing from storage | Check `images/<key>` exists. Restore the file from backup, or the person uploads it again and replaces the picture |
| Save says "This picture is not available" | The id is not the person's own, or it was deleted | The person picks a picture from their own list |
| A photo looks rotated | Orientation is applied on upload from the photo's tag | Upload the picture again. If the tag was missing it cannot be known |
| An API process crashed during an upload | A decoder fault on a hostile file | Treat as a security incident: note the time and the account, restart, and move decoding into its own process (carryover C-95) |

## Mitigation
To stop uploads without affecting anything else, remove the images router from the API. Existing pictures keep working. To stop drawing pictures into PDFs, the worker can be run with `blobs` empty (boxes draw empty).

## Recovery
A missing file can be re-uploaded: the same picture gives the same row. Rows without a file are listed by comparing `resume_images.storage_key` with the files under `images/`. Never delete a row that a document uses.

## Prevention
Every new way a picture can be wrong gets a test first (in `tests/unit/test_image_processing.py`). Keep the accepted types a short list. Check that metadata is gone after any change to the encoder, because the encoders write whatever is left in the image info.
