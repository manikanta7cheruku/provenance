/**
 * The template library. A template is data: how the header is set, how section titles look, where
 * dates go, whether there is a sidebar, which fonts and colors it starts with. One layout function
 * (layout.ts) turns any of them plus the person's words into positioned boxes on the canvas.
 */

export type HeaderLayout = "left" | "center" | "right" | "split" | "band" | "panel";
export type TitleStyle = "rule" | "plain" | "short" | "bar" | "box" | "overline";
export type DatesPlacement = "right" | "below" | "left";

export interface TemplateSpec {
  id: string;
  name: string;
  description: string;
  /** What it is, in a word or two each, for the gallery. */
  tags: string[];
  fontPair: string;
  palette: string;
  margin: number;
  base: number;
  lineHeight: number;
  blockGap: number;
  sectionGap: number;
  header: {
    layout: HeaderLayout;
    nameScale: number;
    nameCaps: boolean;
    nameColor: "ink" | "accent";
    headlineColor: "ink" | "muted" | "accent";
    contacts: "line" | "stack";
    /** Thickness in millimetres of a rule under the header, or 0 for none. */
    rule: number;
  };
  titles: { style: TitleStyle; caps: boolean; color: "ink" | "accent" | "muted"; scale: number; center: boolean };
  dates: DatesPlacement;
  sidebar?: { side: "left" | "right"; width: number; kinds: string[]; fill: "tint" | "accent"; contacts: boolean };
  /** A narrow accent bar down the left edge of every page. */
  edge?: boolean;
}

type Tweaks = Partial<Omit<TemplateSpec, "header" | "titles">> & {
  header?: Partial<TemplateSpec["header"]>;
  titles?: Partial<TemplateSpec["titles"]>;
};

const DEFAULTS: Omit<TemplateSpec, "id" | "name" | "description" | "tags"> = {
  fontPair: "plex-newsreader",
  palette: "navy",
  margin: 16,
  base: 10.5,
  lineHeight: 1.3,
  blockGap: 3,
  sectionGap: 5.5,
  header: { layout: "left", nameScale: 2.4, nameCaps: false, nameColor: "accent", headlineColor: "ink", contacts: "line", rule: 0 },
  titles: { style: "rule", caps: true, color: "accent", scale: 1.05, center: false },
  dates: "right",
};

function make(id: string, name: string, description: string, tags: string[], tweaks: Tweaks): TemplateSpec {
  return {
    ...DEFAULTS,
    ...tweaks,
    id,
    name,
    description,
    tags,
    header: { ...DEFAULTS.header, ...tweaks.header },
    titles: { ...DEFAULTS.titles, ...tweaks.titles },
  };
}

const SIDE_KINDS = ["skills", "education", "certifications", "achievements"];

export const TEMPLATES: readonly TemplateSpec[] = [
  make("ledger", "Ledger", "A serif name and plain headings over thin rules. The traditional, safe choice.", ["Serif", "One column"], {}),
  make("modern-plain", "Modern Plain", "Clean sans serif with blue headings and a thin rule under each.", ["Sans serif", "One column"], {
    fontPair: "inter",
    palette: "ocean",
    header: { nameScale: 2.5 },
  }),
  make("compact-page", "Compact Page", "Tighter type and spacing to fit more on one page. Good for a short history.", ["Dense", "One column"], {
    fontPair: "source",
    palette: "graphite",
    margin: 12,
    base: 9.5,
    blockGap: 1.8,
    sectionGap: 3.8,
    header: { nameScale: 2 },
    titles: { style: "plain", color: "ink" },
  }),
  make("executive", "Executive", "A centered header and spaced capitals between thin rules. Calm and senior.", ["Serif", "Centered"], {
    fontPair: "source-merriweather",
    palette: "slate",
    margin: 18,
    header: { layout: "center", nameScale: 2.3, headlineColor: "muted", rule: 0.8 },
    titles: { style: "overline", color: "ink", center: true },
  }),
  make("graduate", "Graduate", "Friendly sans serif with a short colored line under each heading.", ["Sans serif", "Relaxed"], {
    fontPair: "lato",
    palette: "teal",
    blockGap: 3.6,
    sectionGap: 6.5,
    titles: { style: "short" },
  }),
  make("technical", "Technical", "Dense and plain, with headings in sentence case. Made for skills and projects.", ["Dense", "One column"], {
    fontPair: "source",
    palette: "forest",
    blockGap: 2.4,
    sectionGap: 4.6,
    titles: { style: "plain", caps: false, color: "accent", scale: 1.2 },
  }),
  make("editorial", "Editorial", "A large serif name with a fine rule. For writers, designers and marketers.", ["Serif", "Large name"], {
    fontPair: "playfair-source",
    palette: "burgundy",
    header: { nameScale: 3, headlineColor: "muted", rule: 0.35 },
    titles: { style: "rule" },
  }),
  make("centered-classic", "Centered Classic", "Everything centered, with a short line under each heading.", ["Serif", "Centered"], {
    fontPair: "lora",
    palette: "plum",
    header: { layout: "center", nameScale: 2.6 },
    titles: { style: "short", center: true },
  }),
  make("bold-name", "Bold Name", "A large heavy name in capitals and a small colored bar beside each heading.", ["Sans serif", "Large name"], {
    fontPair: "montserrat-lato",
    palette: "rust",
    header: { nameScale: 2.8, nameCaps: true },
    titles: { style: "bar" },
  }),
  make("right-aligned", "Right Aligned", "The header sits on the right and the body stays on the left.", ["Mixed fonts", "Right header"], {
    fontPair: "inter-lora",
    palette: "navy",
    header: { layout: "right", nameScale: 2.5 },
  }),
  make("quiet-minimal", "Quiet Minimal", "Wide margins and small grey headings. Nothing competes with your words.", ["Sans serif", "Minimal"], {
    fontPair: "lato",
    palette: "mono",
    margin: 22,
    header: { nameScale: 2, nameColor: "ink", headlineColor: "muted" },
    titles: { style: "overline", color: "muted", scale: 0.95 },
  }),
  make("heavy-rule", "Heavy Rule", "A thick line under the header and plain colored headings.", ["Serif", "One column"], {
    fontPair: "merriweather",
    palette: "olive",
    header: { nameScale: 2.3, rule: 1.2 },
    titles: { style: "plain", caps: false, scale: 1.15 },
  }),
  make("classic-serif", "Classic Serif", "Book-style serif throughout, centered header, fine rules.", ["Serif", "Centered"], {
    fontPair: "newsreader",
    palette: "sand",
    header: { layout: "center", nameScale: 2.6, rule: 0.35 },
    base: 11,
  }),

  make("banner", "Banner", "A colored band across the top holds your name and contacts.", ["Sans serif", "Color band"], {
    fontPair: "montserrat-lato",
    palette: "ocean",
    header: { layout: "band", nameScale: 2.6, nameColor: "ink", headlineColor: "ink" },
    titles: { style: "rule" },
  }),
  make("sidebar-left", "Sidebar Left", "A tinted column on the left for contacts, skills and education.", ["Two columns", "Sidebar"], {
    fontPair: "source",
    palette: "slate",
    margin: 14,
    header: { nameScale: 2.4 },
    titles: { style: "rule" },
    dates: "below",
    sidebar: { side: "left", width: 64, kinds: SIDE_KINDS, fill: "tint", contacts: true },
  }),
  make("sidebar-right", "Sidebar Right", "The tinted column sits on the right, so your experience reads first.", ["Two columns", "Sidebar"], {
    fontPair: "inter",
    palette: "teal",
    margin: 14,
    titles: { style: "short" },
    dates: "below",
    sidebar: { side: "right", width: 64, kinds: SIDE_KINDS, fill: "tint", contacts: true },
  }),
  make("dark-sidebar", "Dark Sidebar", "A solid colored column with light text on the left, and the main story beside it.", ["Two columns", "Bold color"], {
    fontPair: "lato",
    palette: "graphite",
    margin: 14,
    titles: { style: "rule" },
    dates: "below",
    sidebar: { side: "left", width: 66, kinds: SIDE_KINDS, fill: "accent", contacts: true },
  }),
  make("split-header", "Split Header", "Name and headline on the left, contacts stacked on the right.", ["Sans serif", "Split header"], {
    fontPair: "inter",
    palette: "navy",
    header: { layout: "split", nameScale: 2.5, contacts: "stack" },
  }),
  make("soft-panel", "Soft Panel", "The header sits on a soft tinted panel above the body.", ["Mixed fonts", "Panel"], {
    fontPair: "inter-lora",
    palette: "sand",
    header: { layout: "panel", nameScale: 2.5 },
    titles: { style: "plain", scale: 1.1 },
  }),
  make("boxed-titles", "Boxed Titles", "Each heading sits in a tinted bar that separates the sections.", ["Sans serif", "Tinted bars"], {
    fontPair: "source",
    palette: "forest",
    titles: { style: "box", color: "accent", scale: 1 },
  }),
  make("timeline", "Timeline", "Dates run down the left edge and the work sits beside them.", ["Sans serif", "Dates on the left"], {
    fontPair: "lato",
    palette: "burgundy",
    dates: "left",
    titles: { style: "rule" },
  }),
  make("ribbon", "Ribbon", "A bold band with the name and contacts, then quiet colored headings.", ["Serif", "Color band"], {
    fontPair: "playfair-source",
    palette: "plum",
    header: { layout: "band", nameScale: 2.8, nameColor: "ink", headlineColor: "ink", contacts: "line" },
    titles: { style: "plain", scale: 1.15, caps: false },
  }),
  make("wide-sidebar", "Wide Sidebar", "A wide tinted column on the right with bars beside the headings.", ["Two columns", "Sidebar"], {
    fontPair: "montserrat-lato",
    palette: "olive",
    margin: 14,
    base: 10,
    titles: { style: "bar", scale: 1 },
    dates: "below",
    sidebar: { side: "right", width: 76, kinds: [...SIDE_KINDS, "projects"], fill: "tint", contacts: true },
  }),
  make("accent-edge", "Accent Edge", "A narrow colored bar runs down the left edge of every page.", ["Serif", "Edge bar"], {
    fontPair: "merriweather",
    palette: "rust",
    margin: 20,
    header: { nameScale: 2.3 },
    titles: { style: "rule", scale: 1 },
    edge: true,
  }),
];

export function templateById(id: string): TemplateSpec | undefined {
  return TEMPLATES.find((t) => t.id === id);
}
