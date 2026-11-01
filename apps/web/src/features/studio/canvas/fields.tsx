import { useEffect, useId, useState } from "react";
import { COLOR_CHOICES } from "./types";

interface NumberFieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  disabled?: boolean;
  onCommit: (value: number) => void;
}

/**
 * A number the person can type, step with the arrow keys or the spin buttons, and read back.
 * It commits every valid change at once, so the page follows as they type, and snaps an
 * out-of-range number to the nearest allowed one when they leave the field.
 */
export function NumberField({ label, value, min, max, step = 0.5, unit, disabled, onCommit }: NumberFieldProps) {
  const id = useId();
  const [text, setText] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setText(String(Math.round(value * 100) / 100));
  }, [value, focused]);

  function commit(raw: string, final: boolean) {
    const parsed = Number(raw);
    if (raw.trim() === "" || Number.isNaN(parsed)) {
      if (final) setText(String(value));
      return;
    }
    const clamped = Math.min(Math.max(parsed, min), max);
    if (final) setText(String(clamped));
    if (clamped !== value) onCommit(clamped);
  }

  return (
    <div className="cv-num">
      <label className="cv-num__label" htmlFor={id}>
        {label}
        {unit ? <span className="cv-num__unit"> ({unit})</span> : null}
      </label>
      <input
        id={id}
        className="cv-num__input"
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        value={text}
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={(event) => {
          setFocused(false);
          commit(event.target.value, true);
        }}
        onChange={(event) => {
          setText(event.target.value);
          commit(event.target.value, false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit((event.target as HTMLInputElement).value, true);
        }}
      />
    </div>
  );
}

interface ColorFieldProps {
  label: string;
  value: string;
  allowNone?: boolean;
  onChange: (value: string) => void;
}

/** A color from the named choices, or a hex code. */
export function ColorField({ label, value, allowNone, onChange }: ColorFieldProps) {
  const id = useId();
  const isHex = /^#[0-9a-f]{6}$/i.test(value);
  const [hex, setHex] = useState(isHex ? value : "#1f3d7a");
  const named = isHex ? "custom" : value;
  return (
    <div className="cv-color">
      <label className="cv-num__label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="cv-select"
        value={named}
        onChange={(event) => onChange(event.target.value === "custom" ? hex : event.target.value)}
      >
        {allowNone ? <option value="none">None</option> : null}
        {COLOR_CHOICES.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
        <option value="custom">Custom code</option>
      </select>
      {isHex ? (
        <input
          aria-label={`${label}, hex code`}
          className="cv-num__input cv-color__hex"
          value={hex}
          onChange={(event) => {
            const v = event.target.value.trim();
            setHex(v);
            if (/^#[0-9a-f]{6}$/i.test(v)) onChange(v.toLowerCase());
          }}
        />
      ) : null}
    </div>
  );
}
