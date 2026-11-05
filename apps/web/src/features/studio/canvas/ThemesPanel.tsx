import { useState } from "react";
import { ApiError } from "../../../lib/api";
import { createTheme, deleteTheme, fetchThemes, lookOf, replaceTheme, sameLook } from "../../../lib/themes-api";
import type { StudioTheme } from "../../../lib/themes-api";
import { useAsync } from "../../../lib/useAsync";
import { ActionButton, Notice, Skeleton, TextField } from "../../../ui";
import type { CanvasStyle } from "./types";

interface ThemesPanelProps {
  style: CanvasStyle;
  fontLabel: (key: string) => string;
  /** Put a saved look on the resume. The resume checks it again when it is saved. */
  onApply: (theme: StudioTheme) => void;
}

/**
 * My themes: save the fonts and colors of this resume under a name, and put them on any resume
 * later. A theme is the look only, so applying one never changes the words.
 */
export function ThemesPanel({ style, fontLabel, onApply }: ThemesPanelProps) {
  const themes = useAsync((signal) => fetchThemes(signal), []);
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [renaming, setRenaming] = useState<{ id: string; name: string; error?: string } | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const data = themes.data;

  function fail(caught: unknown, fallback: string) {
    setMessage(null);
    setProblem(caught instanceof ApiError ? caught.message : fallback);
  }

  async function save() {
    setBusy(true);
    setProblem(null);
    setNameError(undefined);
    try {
      const made = await createTheme({ name, ...lookOf(style) });
      setName("");
      setMessage(`Saved as ${made.name}.`);
      themes.reload();
    } catch (caught) {
      if (caught instanceof ApiError && caught.fields.name) setNameError(caught.fields.name);
      else fail(caught, "The theme could not be saved. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function update(theme: StudioTheme) {
    setBusy(true);
    setProblem(null);
    try {
      await replaceTheme(theme.id, { name: theme.name, ...lookOf(style) });
      setMessage(`${theme.name} now has the look of this resume.`);
      themes.reload();
    } catch (caught) {
      fail(caught, "The theme could not be updated. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function rename() {
    if (!renaming) return;
    const theme = data?.themes.find((t) => t.id === renaming.id);
    if (!theme) return;
    setBusy(true);
    setProblem(null);
    try {
      await replaceTheme(theme.id, { ...lookOf(theme), name: renaming.name });
      setRenaming(null);
      setMessage("Renamed.");
      themes.reload();
    } catch (caught) {
      if (caught instanceof ApiError && caught.fields.name) setRenaming({ ...renaming, error: caught.fields.name });
      else fail(caught, "The theme could not be renamed.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(theme: StudioTheme) {
    setBusy(true);
    setProblem(null);
    try {
      await deleteTheme(theme.id);
      setConfirming(null);
      setMessage(`${theme.name} deleted. Resumes that used it keep their colors.`);
      themes.reload();
    } catch (caught) {
      fail(caught, "The theme could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  const full = data ? data.count >= data.max_themes : false;

  return (
    <fieldset className="cv-fields">
      <legend className="group__title">My themes</legend>
      <p className="field__hint">Save the fonts and colors of this resume under a name, then use them on any resume. A theme never changes your words.</p>
      <form
        className="cv-themesave"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) void save();
        }}
      >
        <TextField label="Name for this theme" value={name} maxLength={40} error={nameError} onChange={(e) => setName(e.target.value)} />
        <ActionButton type="submit" variant="primary" disabled={busy || full || name.trim() === ""}>
          Save this look
        </ActionButton>
      </form>
      {full ? <p className="job__note">You have the most themes you can keep. Delete one to save another.</p> : null}
      <p className="visually-hidden" role="status">
        {message ?? ""}
      </p>
      {message ? <p className="job__note">{message}</p> : null}
      {problem ? (
        <Notice tone="warn">
          <p>{problem}</p>
        </Notice>
      ) : null}
      {themes.error ? (
        <Notice tone="danger" title="Your themes could not be loaded">
          <p>{themes.error.message}</p>
          <p>
            <ActionButton onClick={themes.reload}>Try again</ActionButton>
          </p>
        </Notice>
      ) : !data ? (
        <Skeleton label="Loading your themes" lines={2} />
      ) : data.themes.length === 0 ? (
        <p className="job__note">No saved themes yet.</p>
      ) : (
        <ul className="cv-mythemes" aria-label="Saved themes">
          {data.themes.map((theme) => {
            const current = sameLook(style, theme);
            return (
              <li key={theme.id} className="cv-mytheme">
                <span className="cv-theme__chips" aria-hidden="true">
                  {[theme.accent, theme.ink, theme.muted, theme.tint].map((c) => (
                    <span key={c} style={{ background: c }} />
                  ))}
                </span>
                {renaming?.id === theme.id ? (
                  <form
                    className="cv-themesave"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!busy) void rename();
                    }}
                  >
                    <TextField
                      label={`New name for ${theme.name}`}
                      value={renaming.name}
                      maxLength={40}
                      error={renaming.error}
                      onChange={(e) => setRenaming({ id: theme.id, name: e.target.value })}
                    />
                    <ActionButton type="submit" variant="primary" disabled={busy || renaming.name.trim() === ""}>
                      Save name
                    </ActionButton>
                    <ActionButton onClick={() => setRenaming(null)}>Cancel</ActionButton>
                  </form>
                ) : (
                  <>
                    <span className="cv-mytheme__name">
                      <strong>{theme.name}</strong>
                      <span className="field__hint">{fontLabel(theme.font_pair)}{current ? ", in use on this resume" : ""}</span>
                    </span>
                    <span className="group__tools">
                      <ActionButton aria-label={`Use ${theme.name}`} aria-pressed={current} onClick={() => onApply(theme)}>
                        Use
                      </ActionButton>
                      <ActionButton aria-label={`Update ${theme.name} to the look of this resume`} disabled={busy || current} onClick={() => void update(theme)}>
                        Update
                      </ActionButton>
                      <ActionButton aria-label={`Rename ${theme.name}`} onClick={() => setRenaming({ id: theme.id, name: theme.name })}>
                        Rename
                      </ActionButton>
                      {confirming === theme.id ? (
                        <>
                          <ActionButton aria-label={`Delete it, ${theme.name}`} disabled={busy} onClick={() => void remove(theme)}>
                            Delete it
                          </ActionButton>
                          <ActionButton onClick={() => setConfirming(null)}>Keep</ActionButton>
                        </>
                      ) : (
                        <ActionButton aria-label={`Delete ${theme.name}`} onClick={() => setConfirming(theme.id)}>
                          Delete
                        </ActionButton>
                      )}
                    </span>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}
