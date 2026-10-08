import type { ButtonHTMLAttributes } from "react";

type Variant = "secondary" | "primary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary: the single most important action in a view. secondary: default. ghost: low emphasis. */
  variant?: Variant;
}

export function Button({ variant = "secondary", type = "button", className, ...rest }: ButtonProps) {
  const classes = ["button", variant === "secondary" ? "" : `button--${variant}`, className ?? ""]
    .filter(Boolean)
    .join(" ");
  return <button type={type} className={classes} {...rest} />;
}
