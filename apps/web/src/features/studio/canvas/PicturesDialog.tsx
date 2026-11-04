import { useState } from "react";
import { ApiError } from "../../../lib/api";
import { deleteImage, fetchImages, formatMegabytes, IMAGE_EXTENSIONS, IMAGE_MAX_BYTES, imageUrl, uploadImage } from "../../../lib/images-api";
import type { StudioImage } from "../../../lib/images-api";
import { useAsync } from "../../../lib/useAsync";
import { ActionButton, Dialog, FileDrop, Notice, Skeleton } from "../../../ui";
import { ICON_LABELS, ICON_NAMES, iconSvg } from "./icons";
import type { PictureRef } from "./edit";

/** An icon drawn from its shapes. The markup comes from our own table, never from a person or a file. */
export function IconGlyph({ name, weight = 2, size = 24 }: { name: string; weight?: number; size?: number }) {
  return (
    <span
      className="cv-iconglyph"
      aria-hidden="true"
      style={{ width: size, height: size }}
      dangerouslySetInnerHTML={{ __html: iconSvg(name, weight) }}
    />
  );
}

export function PicturesDialog({
  open,
  onClose,
  onAdd,
  atLimit,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (picture: PictureRef) => void;
  /** The resume already holds as many pictures as it can. */
  atLimit: boolean;
}) {
  const images = useAsync((signal) => fetchImages(signal), []);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const data = images.data;

  async function send(chosen: File) {
    setBusy(true);
    setProblem(undefined);
    try {
      await uploadImage(chosen);
      setFile(null);
      images.reload();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "The picture could not be uploaded. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(image: StudioImage) {
    setRemoveError(null);
    try {
      await deleteImage(image.id);
      images.reload();
    } catch (caught) {
      setRemoveError(caught instanceof ApiError ? caught.message : "The picture could not be deleted.");
    }
  }

  return (
    <Dialog
      open={open}
      title="Pictures"
      onClose={onClose}
      actions={
        <ActionButton variant="primary" onClick={onClose} autoFocus>
          Done
        </ActionButton>
      }
    >
      <p>
        Add a picture to your resume, such as a photo or a logo. Many employers advise against photos, and some hiring systems ignore pictures, so nothing a
        reader needs should be only in a picture.
      </p>
      <FileDrop
        label="Upload a picture"
        hint={`A JPEG, PNG or WebP picture, up to ${formatMegabytes(IMAGE_MAX_BYTES)}. It is checked and drawn again, and the camera, place and time stored in a photo are removed.`}
        extensions={IMAGE_EXTENSIONS}
        maxBytes={IMAGE_MAX_BYTES}
        file={file}
        error={problem}
        disabled={busy}
        onSelect={(chosen) => {
          setFile(chosen);
          void send(chosen);
        }}
        onReject={(message) => {
          setFile(null);
          setProblem(message);
        }}
      />
      {removeError ? (
        <Notice tone="warn">
          <p>{removeError}</p>
        </Notice>
      ) : null}
      {images.error ? (
        <Notice tone="danger" title="Your pictures could not be loaded">
          <p>{images.error.message}</p>
          <p>
            <ActionButton onClick={images.reload}>Try again</ActionButton>
          </p>
        </Notice>
      ) : !data ? (
        <Skeleton label="Loading your pictures" lines={2} />
      ) : data.images.length === 0 ? (
        <p className="job__note">No pictures yet. Upload one above.</p>
      ) : (
        <>
          <p className="job__note">
            {data.count} of {data.max_images} pictures, {formatMegabytes(data.used_bytes)} of {formatMegabytes(data.max_bytes)} used.
            {atLimit ? " This resume already has the most pictures it can hold." : ""}
          </p>
          <ul className="cv-pictures">
            {data.images.map((image) => {
              const name = image.original_name || "Picture";
              return (
                <li key={image.id} className="cv-pictures__item">
                  <img src={imageUrl(image.id)} alt="" className="cv-pictures__thumb" width={72} height={72 * Math.min(1.6, image.height / image.width)} />
                  <span className="cv-pictures__name">
                    {name}
                    <span className="row-sub">
                      {image.width} by {image.height} pixels{image.used ? ". Used in a resume." : "."}
                    </span>
                  </span>
                  <span className="cv-pictures__tools">
                    <ActionButton
                      disabled={atLimit}
                      onClick={() => {
                        onAdd({ id: image.id, width: image.width, height: image.height, name });
                        onClose();
                      }}
                    >
                      Add to page<span className="visually-hidden">: {name}</span>
                    </ActionButton>
                    <ActionButton onClick={() => void remove(image)} disabled={image.used} title={image.used ? "Used in a resume, so it cannot be deleted yet." : undefined}>
                      Delete<span className="visually-hidden">: {name}</span>
                    </ActionButton>
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Dialog>
  );
}

export function IconsDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (name: string) => void }) {
  return (
    <Dialog
      open={open}
      title="Icons"
      onClose={onClose}
      actions={
        <ActionButton variant="primary" onClick={onClose} autoFocus>
          Done
        </ActionButton>
      }
    >
      <p>Small outline icons for contact lines and section headings. They take their color from your style. An icon is decoration: keep the words next to it.</p>
      <ul className="cv-icons">
        {ICON_NAMES.map((name) => (
          <li key={name}>
            <button
              type="button"
              className="cv-icons__button"
              onClick={() => {
                onAdd(name);
                onClose();
              }}
            >
              <IconGlyph name={name} />
              <span>{ICON_LABELS[name]}</span>
              <span className="visually-hidden"> icon, add to page</span>
            </button>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
