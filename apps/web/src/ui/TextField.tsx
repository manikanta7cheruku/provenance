import { forwardRef, useId, useState } from "react";
import type { InputHTMLAttributes } from "react";
import { Icon } from "./Icon";

interface TextFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id"
> {
  label: string;
  /** Help shown before the user types. Linked to the input for screen readers. */
  hint?: string;
  /** Error text. Presence marks the field invalid. Say what to do, not only what is wrong. */
  error?: string | undefined;
  /** For a password: adds a control that shows or hides what was typed. */
  reveal?: boolean;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField({ label, hint, error, reveal, type, ...inputProps }, ref) {
    const id = useId();
    const hintId = `${id}-hint`;
    const errorId = `${id}-error`;
    const [shown, setShown] = useState(false);
    const describedBy = [hint ? hintId : null, error ? errorId : null]
      .filter(Boolean)
      .join(" ");
    const canReveal = reveal && type === "password";
    const input = (
      <input
        ref={ref}
        className={
          canReveal ? "field__input field__input--revealable" : "field__input"
        }
        id={id}
        type={canReveal && shown ? "text" : type}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...inputProps}
      />
    );
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
        {canReveal ? (
          <div className="field__wrap">
            {input}
            <button
              type="button"
              className="field__reveal"
              aria-pressed={shown}
              aria-label={shown ? "Hide password" : "Show password"}
              onClick={() => setShown((value) => !value)}
            >
              <Icon name={shown ? "eyeOff" : "eye"} size={18} />
            </button>
          </div>
        ) : (
          input
        )}
        {error ? (
          <p id={errorId} className="field__error">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
