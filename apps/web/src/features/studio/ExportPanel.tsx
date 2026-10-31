import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { downloadUrl, fetchExports, startExport } from "../../lib/studio-api";
import type { ExportInfo } from "../../lib/studio-api";
import { ActionButton, formatBytes, Notice } from "../../ui";

const POLL_MS = 1500;

interface ExportPanelProps {
  resumeId: string;
  /** Saves the resume first so the PDF matches the screen. Rejects if it cannot be saved. */
  beforeExport: () => Promise<void>;
  /** The person's name, used in the file name shown on the link. */
  fileName: string;
}

export function ExportPanel({ resumeId, beforeExport, fileName }: ExportPanelProps) {
  const [latest, setLatest] = useState<ExportInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchExports(resumeId, controller.signal)
      .then((items) => setLatest(items[0] ?? null))
      .catch(() => undefined);
    return () => controller.abort();
  }, [resumeId]);

  const preparing = latest?.ui_state === "preparing";
  useEffect(() => {
    if (!preparing) return;
    const timer = window.setInterval(() => {
      fetchExports(resumeId)
        .then((items) => setLatest(items[0] ?? null))
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [preparing, resumeId]);

  async function make() {
    setBusy(true);
    setProblem(null);
    try {
      await beforeExport();
      setLatest(await startExport(resumeId));
    } catch (caught) {
      setProblem(
        caught instanceof ApiError
          ? caught.message
          : "The resume could not be saved, so no PDF was made. Fix the problems shown and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="export">
      <ActionButton variant="primary" onClick={() => void make()} disabled={busy || preparing}>
        {preparing ? "Making your PDF" : "Make a PDF"}
      </ActionButton>
      <div role="status" className="export__status">
        {preparing ? <span>This takes a few seconds.</span> : null}
        {latest?.ui_state === "ready" ? (
          <span>
            <a href={downloadUrl(latest.id)} download>
              Download {fileName || "Resume"} Resume.pdf
            </a>{" "}
            ({latest.page_count} {latest.page_count === 1 ? "page" : "pages"}
            {latest.size_bytes !== null ? `, ${formatBytes(latest.size_bytes)}` : ""})
          </span>
        ) : null}
      </div>
      {latest?.ui_state === "failed" ? (
        <Notice tone="danger">
          <p>{latest.error_message}</p>
        </Notice>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
    </div>
  );
}
