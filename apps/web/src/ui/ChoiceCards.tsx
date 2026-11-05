import { useId } from "react";
import "./choice.css";

interface ChoiceOption<T extends string> {
  value: T;
  title: string;
  description: string;
}

interface ChoiceCardsProps<T extends string> {
  legend: string;
  options: readonly ChoiceOption<T>[];
  value: T;
  onChange: (value: T) => void;
  name?: string;
}

/**
 * A few large choices, each with a short explanation. They are real radio buttons in a fieldset, so
 * the arrow keys move between them, a screen reader reads the group and each choice with its
 * description, and the selected one is shown by an outline and a marker, not by color alone.
 */
export function ChoiceCards<T extends string>({ legend, options, value, onChange, name }: ChoiceCardsProps<T>) {
  const group = useId();
  return (
    <fieldset className="choices">
      <legend className="choices__legend">{legend}</legend>
      <div className="choices__grid">
        {options.map((option) => {
          const id = `${group}-${option.value}`;
          return (
            <div key={option.value} className="choice">
              <input
                id={id}
                className="choice__input"
                type="radio"
                name={name ?? group}
                value={option.value}
                checked={value === option.value}
                aria-describedby={`${id}-description`}
                onChange={() => onChange(option.value)}
              />
              <label htmlFor={id} className="choice__card">
                <span className="choice__title">{option.title}</span>
                <span id={`${id}-description`} className="choice__description">
                  {option.description}
                </span>
              </label>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
