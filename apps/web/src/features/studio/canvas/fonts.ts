import { FONT_FILES } from "./css";

/** Wait until the shipped fonts are ready, so text is measured with the fonts that will print. */
export async function loadFonts(): Promise<void> {
  if (typeof document === "undefined" || !document.fonts) return;
  try {
    await Promise.all(FONT_FILES.map(([family, weight, style]) => document.fonts.load(`${style} ${weight} 12px "${family}"`)));
    await document.fonts.ready;
  } catch {
    // A font that cannot load falls back to a system font. The resume is still laid out.
  }
}
