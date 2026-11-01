/**
 * Ready-made color sets. A palette is four colors: the accent used for names and headings, the
 * text color, the grey for dates and contacts, and a soft tint for panels and sidebars. Each one is
 * checked by a test: the text colors are readable on white and on the tint, and the accent is
 * readable on white and carries white text.
 */

export interface Palette {
  id: string;
  name: string;
  accent: string;
  ink: string;
  muted: string;
  tint: string;
}

export const PALETTES: readonly Palette[] = [
  { id: "navy", name: "Navy", accent: "#1f3d7a", ink: "#1b1b1b", muted: "#4a4a4a", tint: "#eef1f6" },
  { id: "graphite", name: "Graphite", accent: "#2b2f36", ink: "#1b1b1b", muted: "#4a4a4a", tint: "#eeeeee" },
  { id: "forest", name: "Forest", accent: "#1f5d3a", ink: "#1b1f1c", muted: "#4a524d", tint: "#eaf2ec" },
  { id: "burgundy", name: "Burgundy", accent: "#7a1f3d", ink: "#231a1d", muted: "#5a4a4f", tint: "#f5ebee" },
  { id: "teal", name: "Teal", accent: "#0f6b6b", ink: "#17201f", muted: "#46514f", tint: "#e6f2f1" },
  { id: "plum", name: "Plum", accent: "#5b2a86", ink: "#1f1a24", muted: "#504a58", tint: "#f1ebf7" },
  { id: "rust", name: "Rust", accent: "#9a3b12", ink: "#241b16", muted: "#594c44", tint: "#f7ece5" },
  { id: "slate", name: "Slate", accent: "#334e68", ink: "#1c232b", muted: "#4b5662", tint: "#e9eef3" },
  { id: "ocean", name: "Ocean", accent: "#0b5cad", ink: "#14202e", muted: "#44546a", tint: "#e8f1fa" },
  { id: "olive", name: "Olive", accent: "#55611c", ink: "#1f2114", muted: "#4f5240", tint: "#f0f1e2" },
  { id: "sand", name: "Sand", accent: "#7a5c1f", ink: "#241f16", muted: "#574d3c", tint: "#f5efe2" },
  { id: "mono", name: "Black and white", accent: "#000000", ink: "#000000", muted: "#404040", tint: "#f2f2f2" },
];

export function paletteById(id: string): Palette {
  return PALETTES.find((p) => p.id === id) ?? PALETTES[0]!;
}

/** The palette whose four colors match a style, or null when the person mixed their own. */
export function matchingPalette(style: { accent: string; ink: string; muted: string; tint: string }): Palette | null {
  return (
    PALETTES.find((p) => p.accent === style.accent && p.ink === style.ink && p.muted === style.muted && p.tint === style.tint) ?? null
  );
}
