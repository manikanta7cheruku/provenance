/** Words on the studio screens. Field names depend on the kind of section. */

interface BlockLabels {
  heading: string;
  subheading: string;
  dates: string;
  location: string;
  body: string;
  bodyHint: string;
  /** Fields the section does not use are hidden. */
  show: { heading: boolean; subheading: boolean; dates: boolean; location: boolean };
}

const ALL = { heading: true, subheading: true, dates: true, location: true };

const DEFAULT: BlockLabels = {
  heading: "Heading",
  subheading: "Subheading",
  dates: "Dates",
  location: "Place",
  body: "Details",
  bodyHint: "Use the buttons for bold, lists and highlights.",
  show: ALL,
};

export const BLOCK_LABELS: Record<string, BlockLabels> = {
  summary: { ...DEFAULT, body: "Summary", bodyHint: "Two or three lines on who you are and what you want.", show: { heading: false, subheading: false, dates: false, location: false } },
  experience: { ...DEFAULT, heading: "Role", subheading: "Company", bodyHint: "One achievement per bullet. Say what you did and what changed." },
  education: { ...DEFAULT, heading: "Degree or course", subheading: "Institution", body: "Details", show: { ...ALL, location: false } },
  projects: { ...DEFAULT, heading: "Project name", subheading: "Technologies", show: { ...ALL, location: false } },
  skills: { ...DEFAULT, heading: "Group (optional)", body: "Skills", bodyHint: "For example: Python, SQL, Power BI.", show: { heading: true, subheading: false, dates: false, location: false } },
  certifications: { ...DEFAULT, heading: "Certification", subheading: "Issued by", dates: "Date", body: "Details", show: { ...ALL, location: false } },
  achievements: { ...DEFAULT, heading: "Achievement", dates: "Date", show: { heading: true, subheading: false, dates: true, location: false } },
  custom: DEFAULT,
};

export function blockLabels(kind: string): BlockLabels {
  return BLOCK_LABELS[kind] ?? DEFAULT;
}

export const KIND_LABELS: Record<string, string> = {
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  skills: "Skills",
  certifications: "Certifications",
  achievements: "Achievements",
  custom: "Custom section",
};

export const OPTION_LABELS: Record<string, Record<string, string>> = {
  size: { small: "Small", medium: "Medium", large: "Large" },
  spacing: { tight: "Tight", normal: "Normal", relaxed: "Relaxed" },
  margins: { narrow: "Narrow", normal: "Normal", wide: "Wide" },
  divider: { none: "No line", thin: "Thin line", bold: "Bold line", dotted: "Dotted line" },
  paper: { a4: "A4", letter: "US Letter" },
};

const SAVE_TEXT: Record<string, string> = {
  saved: "All changes saved",
  unsaved: "Changes not saved yet",
  saving: "Saving",
  error: "Could not save. Fix the problems shown, and it will save again.",
  conflict: "This resume was changed somewhere else.",
};

export function saveText(state: string, at: Date | null): string {
  if (state === "saved" && at) {
    return `All changes saved at ${at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }
  return SAVE_TEXT[state] ?? "";
}
