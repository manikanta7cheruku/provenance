// Mechanical check of the frontend dependency rules (docs/adr/0019).
//   ui        -> nothing outside ui
//   lib       -> nothing outside lib
//   features  -> ui, lib, and its own feature folder (never another feature)
//   app       -> anything
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";

const SRC = resolve("src");
const ALLOWED = {
  ui: ["ui"],
  lib: ["lib"],
  features: ["features", "ui", "lib"],
  app: ["app", "features", "ui", "lib"],
};

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(ts|tsx)$/.test(name)) yield full;
  }
}

const violations = [];
for (const file of walk(SRC)) {
  const parts = relative(SRC, file).split(sep);
  const area = parts[0];
  if (!(area in ALLOWED)) continue; // files directly in src (main.tsx) may import anything
  const text = readFileSync(file, "utf8");
  for (const match of text.matchAll(/from\s+["'](\.[^"']*)["']/g)) {
    const target = relative(SRC, resolve(dirname(file), match[1])).split(sep);
    const targetArea = target[0];
    if (!ALLOWED[area].includes(targetArea)) {
      violations.push(`${relative(SRC, file)} imports ${match[1]} (${area} must not import ${targetArea})`);
    } else if (area === "features" && targetArea === "features" && target[1] !== parts[1]) {
      violations.push(`${relative(SRC, file)} imports ${match[1]} (a feature must not import another feature)`);
    }
  }
}

if (violations.length > 0) {
  console.error("Boundary violations:\n" + violations.map((v) => "  " + v).join("\n"));
  process.exit(1);
}
console.log("Boundaries OK");
