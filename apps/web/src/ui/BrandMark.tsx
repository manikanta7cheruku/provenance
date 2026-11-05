import { useId } from "react";

/**
 * The Provenance mark: a rounded square in the one brand gradient, a "P" made of a stem and a
 * bowl, and a small brass dot where a receipt would be punched. It is decoration next to the
 * word, so it is hidden from assistive technology. The colors come from tokens.
 */
export function BrandMark({ size = 28 }: { size?: number }) {
  const gradient = useId();
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" className="brand-mark__start" />
          <stop offset="1" className="brand-mark__end" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradient})`} />
      <path className="brand-mark__letter" d="M11 8.5h6.2a5.3 5.3 0 0 1 0 10.6H14.2V24H11V8.5Zm3.2 3v4.6h2.8a2.3 2.3 0 0 0 0-4.6h-2.8Z" />
      <circle className="brand-mark__dot" cx="23.2" cy="23.4" r="1.9" />
    </svg>
  );
}
