import { useId } from "react";
import "./controls.css";

interface Option<T extends string> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string> {
  /** Names the group for assistive technology. Shown only when `showLegend` is set. */
  legend: string;
  showLegend?: boolean;
  options: readonly Option<T>[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * A single choice among a few options, built on native radio inputs so the arrow keys, Tab
 * behavior and screen reader semantics come from the browser.
 */
export function SegmentedControl<T extends string>({
  legend,
  showLegend = false,
  options,
  value,
  onChange,
}: SegmentedControlProps<T>) {
  const name = useId();
  return (
    <fieldset className="segmented">
      <legend className={showLegend ? "segmented__legend" : "visually-hidden"}>{legend}</legend>
      <div className="segmented__options">
        {options.map((option) => (
          <label key={option.value} className="segmented__option">
            <input
              className="segmented__input"
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span className="segmented__label">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
