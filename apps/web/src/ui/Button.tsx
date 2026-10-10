import type { ButtonHTMLAttributes } from "react";

type Variant = "secondary" | "primary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary: the single most important action in a view. secondary: default. ghost: low emphasis. */
  variant?: Variant;
  /** Work is in progress. The button is disabled and announces that it is busy. */
  busy?: boolean;
}

export function Button({
  variant = "secondary",
  type = "button",
  busy = false,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  const classes = ["button", variant === "secondary" ? "" : `button--${variant}`, className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    />
  );
}
