// The frontend must not invent states (docs/adr/0022). The backend owns the vocabulary:
//   packages/domain/src/pv_domain/states.py  class UiState
// This script compares it, in order, with UI_STATES in src/lib/states.ts and fails CI on any
// difference. It reads source text, so it needs no Python and no extra dependency.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const PY = resolve("../../packages/domain/src/pv_domain/states.py");
const TS = resolve("src/lib/states.ts");

function backendStates(text) {
  const block = text.match(/class UiState\(StrEnum\):\n((?:[ ]{4}[A-Z_]+ = "[a-z_]+"\n)+)/);
  if (!block) throw new Error("Could not find `class UiState(StrEnum)` in states.py");
  return [...block[1].matchAll(/= "([a-z_]+)"/g)].map((m) => m[1]);
}

function frontendStates(text) {
  const block = text.match(/UI_STATES\s*=\s*\[([\s\S]*?)\]\s*as const/);
  if (!block) throw new Error("Could not find `UI_STATES = [...] as const` in states.ts");
  return [...block[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
}

const backend = backendStates(readFileSync(PY, "utf8"));
const frontend = frontendStates(readFileSync(TS, "utf8"));

const missing = backend.filter((s) => !frontend.includes(s));
const extra = frontend.filter((s) => !backend.includes(s));
const sameOrder = backend.length === frontend.length && backend.every((s, i) => s === frontend[i]);

if (missing.length || extra.length || !sameOrder) {
  console.error("UI state mismatch between backend and frontend:");
  if (missing.length) console.error("  missing in frontend: " + missing.join(", "));
  if (extra.length) console.error("  not in backend:      " + extra.join(", "));
  if (!missing.length && !extra.length) console.error("  same members, different order");
  process.exit(1);
}
console.log(`States OK (${backend.length}): ${backend.join(", ")}`);
