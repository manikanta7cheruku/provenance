import { useId, useState } from "react";
import type { KeyboardEvent } from "react";
import { Icon } from "./Icon";

interface ChipPickerProps {
  legend: string;
  /** One short line of help. Leave it out when the legend says enough. */
  hint?: string;
  options: readonly { value: string; label: string }[];
  values: string[];
  onChange: (values: string[]) => void;
  /** Only one chip can be on. Pressing the one that is on turns it off (the answer is blank). */
  single?: boolean;
  /** Let the person type their own value. Own values show as chips too. */
  custom?: { placeholder: string } | undefined;
  error?: string | undefined;
}

/**
 * Choices drawn as chips: press to turn on, press again to turn off. Options first, so most people
 * never type. Each chip is a real button with aria-pressed, so keyboards and screen readers get the
 * same answer a mouse does.
 */
export function ChipPicker({ legend, hint, options, values, onChange, single, custom, error }: ChipPickerProps) {
  const id = useId();
  const [draft, setDraft] = useState("");
  const known = new Set(options.map((option) => option.value));
  const own = values.filter((value) => !known.has(value));

  function toggle(value: string) {
    if (single) onChange(values.includes(value) ? [] : [value]);
    else onChange(values.includes(value) ? values.filter((v) => v !== value) : [...values, value]);
  }

  function addDraft() {
    const text = draft.trim().replace(/\s+/g, " ");
    if (!text) return;
    const exists = [...options.map((o) => o.value), ...values].some((v) => v.toLowerCase() === text.toLowerCase());
    if (!exists) onChange(single ? [text] : [...values, text]);
    setDraft("");
  }

  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault(); // inside a form, Enter adds the chip instead of saving the form
      addDraft();
    }
  }

  return (
    <fieldset className="picker" aria-describedby={hint ? `${id}-hint` : undefined}>
      <legend className="picker__legend">{legend}</legend>
      {hint ? (
        <p id={`${id}-hint`} className="field__hint">
          {hint}
        </p>
      ) : null}
      <div className="picker__chips">
        {options.map((option) => {
          const on = values.includes(option.value);
          return (
            <button key={option.value} type="button" className="chip" aria-pressed={on} onClick={() => toggle(option.value)}>
              {on ? <Icon name="check" size={14} /> : null}
              {option.label}
            </button>
          );
        })}
        {own.map((value) => (
          <button key={value} type="button" className="chip" aria-pressed onClick={() => toggle(value)}>
            <Icon name="check" size={14} />
            {value}
          </button>
        ))}
      </div>
      {custom ? (
        <div className="picker__add">
          <input
            className="picker__input"
            aria-label={`Add your own: ${legend}`}
            placeholder={custom.placeholder}
            value={draft}
            maxLength={80}
            autoComplete="off"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKey}
          />
          <button type="button" className="chip chip--add" onClick={addDraft} disabled={!draft.trim()}>
            <Icon name="plus" size={14} />
            Add
          </button>
        </div>
      ) : null}
      {error ? (
        <p className="field__error" role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
