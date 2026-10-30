// Mechanical check of the design-system rule "raw values in component CSS are a defect".
// Colors, shadows and font stacks live in src/ui/tokens.css. Everything else uses token names.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const SRC = resolve("src");
const TOKENS = join(SRC, "ui", "tokens.css");

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (name.endsWith(".css")) yield full;
  }
}

const RULES = [
  [/#[0-9a-fA-F]{3,8}\b/, "hex color"],
  [/\brgba?\(/, "rgb color"],
  [/\bhsla?\(/, "hsl color"],
  [/\bcolor-mix\(/, "color-mix (use a token)"],
  [/box-shadow:(?![^;]*var\()(?!\s*none)/, "raw box-shadow (use --shadow-overlay or a token color)"],
  [/font-family:(?!\s|var\(|inherit)|font-family:\s+(?!var\(|inherit)/, "raw font-family (use --font-ui, --font-display or --font-mono)"],
  [/\b(Canvas|CanvasText|ButtonText|LinkText)\b(?!.*forced-colors)/, "system color outside a forced-colors block"],
];

const violations = [];
for (const file of walk(SRC)) {
  if (file === TOKENS || file.endsWith("fonts.css")) continue;
  const lines = readFileSync(file, "utf8").split("\n");
  let inForcedColors = false;
  lines.forEach((line, index) => {
    if (line.includes("@media (forced-colors")) inForcedColors = true;
    if (inForcedColors) return; // forced-colors blocks must use system colors
    for (const [pattern, label] of RULES) {
      if (pattern.test(line)) violations.push(`${relative(SRC, file)}:${index + 1} ${label}: ${line.trim()}`);
    }
  });
}

if (violations.length > 0) {
  console.error("Raw design values outside tokens.css:\n" + violations.map((v) => "  " + v).join("\n"));
  process.exit(1);
}
console.log("Tokens OK");
