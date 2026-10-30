import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import "./controls.css";

interface FieldProps {
  label: string;
  /** Help shown before the user types. Linked to the control for screen readers. */
  hint?: string;
  /** Error text. Presence marks the field invalid. Say what to do, not only what is wrong. */
  error?: string | undefined;
}

interface Wiring {
  id: string;
  describedBy: string | undefined;
  invalid: true | undefined;
}

function FieldFrame({ label, hint, error, children }: FieldProps & { children: (wiring: Wiring) => ReactNode }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {hint ? (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      ) : null}
      {children({ id, describedBy, invalid: error ? true : undefined })}
      {error ? (
        <p id={errorId} className="field__error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextArea({
  label,
  hint,
  error,
  ...rest
}: FieldProps & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id">) {
  return (
    <FieldFrame label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <textarea
          className="field__input field__input--multiline"
          id={id}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          {...rest}
        />
      )}
    </FieldFrame>
  );
}

export function Select({
  label,
  hint,
  error,
  children,
  ...rest
}: FieldProps & Omit<SelectHTMLAttributes<HTMLSelectElement>, "id">) {
  return (
    <FieldFrame label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <select
          className="field__input field__input--select"
          id={id}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          {...rest}
        >
          {children}
        </select>
      )}
    </FieldFrame>
  );
}

export function Checkbox({
  label,
  hint,
  error,
  ...rest
}: FieldProps & Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "type">) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="check">
      <input
        className="check__input"
        id={id}
        type="checkbox"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      <div>
        <label className="check__label" htmlFor={id}>
          {label}
        </label>
        {hint ? (
          <p id={hintId} className="field__hint">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={errorId} className="field__error">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
