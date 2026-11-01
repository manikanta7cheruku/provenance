import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/api";
import { previewResume, saveResume } from "../../lib/studio-api";
import type { ResumeContent } from "../../lib/studio-api";
import { sameDocument } from "./doc-ops";

export type SaveState = "saved" | "unsaved" | "saving" | "error" | "conflict";

const SAVE_DELAY_MS = 1500;
const PREVIEW_DELAY_MS = 500;

/**
 * Holds the resume being edited and keeps it saved.
 *
 * Saves are automatic after a pause in typing, one at a time. Each save says which revision it
 * started from, so a save from an old tab is refused (conflict) instead of overwriting newer work.
 * If the person keeps typing during a save, another save follows. `flush` saves right now, which
 * the export button uses so the PDF matches what is on screen.
 */
interface Editable<T> {
  id: string;
  revision: number;
  content: T;
}

export function useStudioDocument<T extends object>(initial: Editable<T>) {
  const [content, setContentState] = useState<T>(initial.content);
  const [revision, setRevision] = useState(initial.revision);
  const [state, setState] = useState<SaveState>("saved");
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  const latest = useRef(content);
  const saved = useRef(initial.content);
  const rev = useRef(initial.revision);
  const inflight = useRef<Promise<void> | null>(null);
  const timer = useRef<number | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const runSave = useCallback(async (): Promise<void> => {
    if (inflight.current) return inflight.current;
    if (sameDocument(latest.current, saved.current)) {
      setState("saved");
      return;
    }
    const sending = latest.current;
    const job = (async () => {
      setState("saving");
      try {
        const result = await saveResume(initial.id, { content: sending, revision: rev.current });
        rev.current = result.revision;
        saved.current = sending;
        if (alive.current) {
          setRevision(result.revision);
          setProblems({});
          setSavedAt(new Date());
        }
      } catch (caught) {
        if (alive.current) {
          if (caught instanceof ApiError && caught.code === "REVISION_CONFLICT") setState("conflict");
          else {
            setProblems(caught instanceof ApiError ? caught.fields : {});
            setState("error");
          }
        }
        throw caught;
      } finally {
        inflight.current = null;
      }
    })();
    inflight.current = job;
    await job;
    if (alive.current) {
      if (sameDocument(latest.current, saved.current)) setState("saved");
      else {
        setState("unsaved");
        await runSave();
      }
    }
  }, [initial.id]);

  const schedule = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      runSave().catch(() => undefined);
    }, SAVE_DELAY_MS);
  }, [runSave]);

  const setContent = useCallback(
    (next: T | ((current: T) => T)) => {
      const value = typeof next === "function" ? next(latest.current) : next;
      latest.current = value;
      setContentState(value);
      setState((s) => (s === "conflict" ? s : "unsaved"));
      schedule();
    },
    [schedule],
  );

  /** Save now. Resolves when the stored copy matches the screen, rejects if it could not be saved. */
  const flush = useCallback(async () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    if (inflight.current) await inflight.current.catch(() => undefined);
    await runSave();
  }, [runSave]);

  /** Replace everything with a document from the server (after a restore or a reload). */
  const replace = useCallback((doc: { revision: number; content: T }) => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    latest.current = doc.content;
    saved.current = doc.content;
    rev.current = doc.revision;
    setContentState(doc.content);
    setRevision(doc.revision);
    setProblems({});
    setState("saved");
  }, []);

  // Do not lose the last edit when the tab is closed or the screen changes.
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!sameDocument(latest.current, saved.current)) {
        event.preventDefault();
        void runSave().catch(() => undefined);
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
      if (timer.current !== null) window.clearTimeout(timer.current);
      if (!sameDocument(latest.current, saved.current)) void runSave().catch(() => undefined);
    };
  }, [runSave]);

  const getRevision = useCallback(() => rev.current, []);

  return { content, setContent, revision, state, problems, savedAt, flush, replace, getRevision };
}

/** The server-made HTML of the current content, refreshed after a short pause. */
export function usePreview(id: string, content: ResumeContent) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      previewResume(id, content, controller.signal)
        .then((result) => {
          setHtml(result.html);
          setFailed(false);
        })
        .catch((caught: unknown) => {
          if (controller.signal.aborted) return;
          // Keep the last good preview. A document with a problem is explained by the editor.
          setFailed(!(caught instanceof ApiError && caught.status === 422));
        });
    }, html === null ? 0 : PREVIEW_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // `html` is read only to skip the delay for the first render.
  }, [id, content]);

  return { html, failed };
}
