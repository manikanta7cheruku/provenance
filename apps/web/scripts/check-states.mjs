// The frontend must not invent states (docs/adr/0022). The backend owns the vocabulary:
//   packages/domain/src/pv_domain/states.py  the state classes listed below
// This script compares each, in order, with the matching list in src/lib/states.ts and fails CI
// on any difference. It reads source text, so it needs no Python and no extra dependency.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const DOMAIN = resolve("../../packages/domain/src/pv_domain");
const TS = resolve("src/lib/states.ts");

const PAIRS = [
  { file: "states.py", pythonClass: "UiState", tsList: "UI_STATES" },
  { file: "states.py", pythonClass: "ResumeUiState", tsList: "RESUME_UI_STATES" },
  { file: "states.py", pythonClass: "JobUiState", tsList: "JOB_UI_STATES" },
  { file: "eligibility.py", pythonClass: "EligibilityState", tsList: "ELIGIBILITY_STATES" },
  { file: "analysis.py", pythonClass: "AnalysisUiState", tsList: "ANALYSIS_UI_STATES" },
  { file: "analysis.py", pythonClass: "Verdict", tsList: "VERDICTS" },
  { file: "analysis.py", pythonClass: "Band", tsList: "BANDS" },
];

function backendStates(text, pythonClass) {
  const members = String.raw`\(StrEnum\):\n((?:[ ]{4}[A-Z_]+ = "[a-z_]+"\n)+)`;
  const block = text.match(new RegExp(`class ${pythonClass}` + members));
  if (!block) throw new Error(`Could not find class ${pythonClass}(StrEnum) in states.py`);
  return [...block[1].matchAll(/= "([a-z_]+)"/g)].map((m) => m[1]);
}

function frontendStates(text, tsList) {
  const tail = String.raw`\s*=\s*\[([\s\S]*?)\]\s*as const`;
  const block = text.match(new RegExp(tsList + tail));
  if (!block) throw new Error(`Could not find ${tsList} = [...] as const in states.ts`);
  return [...block[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
}

const typescript = readFileSync(TS, "utf8");
let failed = false;

for (const { file, pythonClass, tsList } of PAIRS) {
  const backend = backendStates(readFileSync(resolve(DOMAIN, file), "utf8"), pythonClass);
  const frontend = frontendStates(typescript, tsList);
  const missing = backend.filter((s) => !frontend.includes(s));
  const extra = frontend.filter((s) => !backend.includes(s));
  const sameOrder = backend.length === frontend.length && backend.every((s, i) => s === frontend[i]);
  if (missing.length || extra.length || !sameOrder) {
    failed = true;
    console.error(`${pythonClass} and ${tsList} differ:`);
    if (missing.length) console.error("  missing in frontend: " + missing.join(", "));
    if (extra.length) console.error("  not in backend:      " + extra.join(", "));
    if (!missing.length && !extra.length) console.error("  same members, different order");
  } else {
    console.log(`States OK, ${pythonClass} (${backend.length}): ${backend.join(", ")}`);
  }
}
if (failed) process.exit(1);
