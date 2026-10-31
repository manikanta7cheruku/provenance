/** Contrast of a color on white paper. The server enforces the same rule (WCAG, 4.5 for text). */
export const MIN_ACCENT_CONTRAST = 4.5;

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function isHexColor(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

export function contrastOnWhite(hex: string): number {
  const r = channel(parseInt(hex.slice(1, 3), 16));
  const g = channel(parseInt(hex.slice(3, 5), 16));
  const b = channel(parseInt(hex.slice(5, 7), 16));
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return 1.05 / (luminance + 0.05);
}

/** A sentence about the color, or null when it is fine. */
export function accentProblem(value: string): string | null {
  if (!isHexColor(value)) return "Use a color like #1f3d7a.";
  if (contrastOnWhite(value) < MIN_ACCENT_CONTRAST) {
    return "This color is too light to read on white paper. Choose a darker one.";
  }
  return null;
}

/** Colors that pass, named so a person can choose without knowing hex codes. */
export const ACCENT_PRESETS = [
  { value: "#222222", label: "Charcoal" },
  { value: "#1f3d7a", label: "Navy" },
  { value: "#7a1f3d", label: "Wine" },
  { value: "#1f6b4a", label: "Forest" },
  { value: "#5b3a8c", label: "Plum" },
  { value: "#8a4b0f", label: "Rust" },
] as const;
