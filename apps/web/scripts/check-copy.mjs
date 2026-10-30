// Mechanical check of the writing rules: no em dashes and no stock marketing or AI-template phrases
// in product copy, documentation or code comments. A line that states the rule itself can opt out
// with the marker "copy-check: allow" (see docs/product/ux-specification.md).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const SKIP_DIRS = new Set(["node_modules", ".venv", "dist", ".git", "test-results", "playwright-report", ".mypy_cache", ".ruff_cache", ".pytest_cache", "__pycache__", ".import_linter_cache"]);
const SKIP_FILES = new Set(["uv.lock", "package-lock.json", "check-copy.mjs", "PR_DESCRIPTION.md"]);
const EXTENSIONS = /\.(md|ts|tsx|css|html|py|ps1|ya?ml|toml|mjs|js|sql|txt|example)$/;

const EM_DASH = String.fromCodePoint(0x2014);
const EN_DASH = String.fromCodePoint(0x2013);
const SPARKLES = String.fromCodePoint(0x2728);

const RULES = [
  [new RegExp(EM_DASH), "em dash"],
  [new RegExp(` ${EN_DASH} `), "en dash used as a dash"],
  [new RegExp(SPARKLES), "sparkles emoji"],
  [/\b(seamless(ly)?|leverag(e|es|ed|ing)|unlock(s|ed|ing)?|supercharg\w*|game[- ]chang\w*|cutting[- ]edge|revolutioniz\w*|delve|elevate your|next[- ]generation|ai[- ]powered|powered by ai)\b/i, "stock marketing or AI-template phrase"],
];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (EXTENSIONS.test(name) && !SKIP_FILES.has(name)) yield full;
  }
}

const violations = [];
for (const file of walk(ROOT)) {
  readFileSync(file, "utf8")
    .split("\n")
    .forEach((line, index) => {
      if (line.includes("copy-check: allow")) return;
      for (const [pattern, label] of RULES) {
        if (pattern.test(line)) violations.push(`${relative(ROOT, file)}:${index + 1} ${label}: ${line.trim().slice(0, 120)}`);
      }
    });
}

if (violations.length > 0) {
  console.error("Writing rule violations:\n" + violations.map((v) => "  " + v).join("\n"));
  process.exit(1);
}
console.log("Copy OK");
