// Computes WCAG 2.2 contrast for the token pairs the interface uses, in both themes.
// Reads src/ui/tokens.css (light-dark(light, dark) pairs) so the check can never drift from the
// real values. Text pairs need 4.5:1, non-text pairs (control edges, focus, status dots) 3:1.
import { readFileSync } from "node:fs";

const css = readFileSync("src/ui/tokens.css", "utf8");

/** name -> { light, dark } for every color token written as light-dark(a, b) or a plain hex. */
function parseTokens(text) {
  const tokens = new Map();
  for (const match of text.matchAll(/(--[\w-]+):\s*([^;]+);/g)) {
    const [, name, value] = match;
    const pair = value.match(/^light-dark\(\s*(#[0-9a-fA-F]{3,8}|rgb\([^)]*\))\s*,\s*(#[0-9a-fA-F]{3,8}|rgb\([^)]*\))\s*\)/);
    if (pair) tokens.set(name, { light: pair[1], dark: pair[2] });
    else if (/^#[0-9a-fA-F]{3,8}$/.test(value.trim())) tokens.set(name, { light: value.trim(), dark: value.trim() });
    else {
      const ref = value.trim().match(/^var\((--[\w-]+)\)$/);
      if (ref) tokens.set(name, { ref: ref[1] });
    }
  }
  return tokens;
}

const tokens = parseTokens(css);

function resolve(name, mode) {
  const entry = tokens.get(name);
  if (!entry) throw new Error(`Unknown token ${name}`);
  if (entry.ref) return resolve(entry.ref, mode);
  return entry[mode];
}

function toRgb(value) {
  const hex = value.match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (!hex) throw new Error(`Cannot compute contrast for ${value}`);
  let digits = hex[1];
  if (digits.length === 3) digits = [...digits].map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(digits.slice(i, i + 2), 16) / 255);
}

function luminance([r, g, b]) {
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrast(foreground, background) {
  const a = luminance(toRgb(foreground));
  const b = luminance(toRgb(background));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const SURFACES = ["--color-surface-base", "--color-surface-raised", "--color-surface-sunken"];
const TEXT = 4.5;
const NON_TEXT = 3;

/** [foreground, background, minimum ratio, what it protects] */
const PAIRS = [
  ...SURFACES.map((s) => ["--color-text-primary", s, TEXT, "body text"]),
  ["--color-text-primary", "--color-selected", TEXT, "text on a selected row"],
  ...SURFACES.map((s) => ["--color-text-secondary", s, TEXT, "supporting text"]),
  ["--color-text-secondary", "--color-selected", TEXT, "supporting text on a selected row"],
  ...SURFACES.map((s) => ["--color-accent", s, TEXT, "links and accent text"]),
  ["--color-accent", "--color-accent-subtle", TEXT, "accent text on the selected tint"],
  ["--color-text-on-accent", "--color-accent", TEXT, "primary button"],
  ["--color-text-on-accent", "--color-accent-hover", TEXT, "primary button hover"],
  ["--color-text-on-accent", "--color-accent-active", TEXT, "primary button pressed"],
  ["--color-text-on-danger", "--color-danger-fill", TEXT, "destructive button"],
  ...["--color-success", "--color-warning", "--color-danger", "--color-info"].flatMap((c) =>
    ["--color-surface-base", "--color-surface-raised"].map((s) => [c, s, TEXT, "status text"]),
  ),
  ...["--color-border-control", "--color-focus"].flatMap((c) =>
    SURFACES.map((s) => [c, s, NON_TEXT, "control edge or focus ring"]),
  ),
  ...["--color-success", "--color-warning", "--color-danger", "--color-info", "--color-text-secondary"].map((c) => [
    c,
    "--color-surface-base",
    NON_TEXT,
    "status dot",
  ]),
];

const failures = [];
let checked = 0;
for (const mode of ["light", "dark"]) {
  for (const [fg, bg, minimum, what] of PAIRS) {
    const ratio = contrast(resolve(fg, mode), resolve(bg, mode));
    checked += 1;
    if (ratio < minimum) {
      failures.push(`${mode}: ${fg} on ${bg} is ${ratio.toFixed(2)}:1, needs ${minimum}:1 (${what})`);
    }
  }
}

if (failures.length > 0) {
  console.error("Contrast failures:\n" + failures.map((f) => "  " + f).join("\n"));
  process.exit(1);
}
console.log(`Contrast OK (${checked} pairs, light and dark)`);
