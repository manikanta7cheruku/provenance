import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "quiet" | "danger";

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/** A plain button for actions in data screens. Meaning comes from the label, not from color. */
export function ActionButton({ variant = "quiet", className, ...rest }: ActionButtonProps) {
  return (
    <button type="button" className={`action action--${variant}${className ? ` ${className}` : ""}`} {...rest} />
  );
}
