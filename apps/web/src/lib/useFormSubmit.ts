import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export interface FormNotice {
  tone: "info" | "warn" | "danger";
  text: string;
}

/**
 * Submission state shared by every form: busy flag, field errors from the server,
 * a form-level notice, rate limit back-off, and focus on the first invalid field.
 * Holds no markup, so features render it however their screen needs.
 */
export function useFormSubmit() {
  const formRef = useRef<HTMLFormElement>(null);
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<FormNotice | null>(null);
  const [blockedUntil, setBlockedUntil] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);

  // After a failed attempt, move focus to the first invalid field so keyboard and
  // screen reader users land on the problem.
  useEffect(() => {
    if (attempt === 0) return;
    formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [attempt]);

  // Re-enable the form when the rate limit window has passed.
  useEffect(() => {
    if (blockedUntil === null) return;
    const delay = Math.max(0, blockedUntil - Date.now());
    const timer = window.setTimeout(() => {
      setBlockedUntil(null);
      setNotice(null);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [blockedUntil]);

  const submit = useCallback(
    async (clientErrors: Record<string, string>, action: () => Promise<void>) => {
      if (Object.keys(clientErrors).length > 0) {
        setFieldErrors(clientErrors);
        setNotice(null);
        setAttempt((count) => count + 1);
        return;
      }
      setBusy(true);
      setFieldErrors({});
      setNotice(null);
      try {
        await action();
      } catch (error) {
        if (error instanceof ApiError) {
          if (error.status === 422 && Object.keys(error.fields).length > 0) {
            setFieldErrors(error.fields);
            setAttempt((count) => count + 1);
          } else if (error.status === 429) {
            const seconds = error.retryAfterSeconds ?? 60;
            setBlockedUntil(Date.now() + seconds * 1000);
            setNotice({
              tone: "warn",
              text: `Too many attempts. Try again in about ${seconds} seconds.`,
            });
          } else {
            setNotice({ tone: "danger", text: error.message });
          }
        } else {
          setNotice({
            tone: "danger",
            text: "Something unexpected happened. Your data is safe. Try again.",
          });
        }
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  return { formRef, busy, blocked: blockedUntil !== null, fieldErrors, notice, submit, setNotice };
}
