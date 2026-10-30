import type { EntrySpec, ProfileEntry } from "../../lib/profile-api";

export interface EntrySummary {
  title: string;
  subtitle: string;
  detail: string;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function period(data: Record<string, unknown>): string {
  const start = text(data.start_date);
  const end = text(data.end_date);
  if (start && end) return `${start} to ${end}`;
  return start ? `From ${start}` : end;
}

function join(parts: string[]): string {
  return parts.filter(Boolean).join(" · ");
}

/** One plain line each for the heading, the supporting line and a short detail of an entry. */
export function summarize(entry: ProfileEntry, spec: EntrySpec | undefined): EntrySummary {
  const data = entry.data;
  const title = text(data[spec?.primary_field ?? ""]) || "Untitled";
  switch (entry.entry_type) {
    case "education":
      return {
        title,
        subtitle: join([text(data.degree), text(data.field_of_study), period(data)]),
        detail: text(data.grade) ? `Grade: ${text(data.grade)}` : "",
      };
    case "work":
    case "internship": {
      const highlights = Array.isArray(data.highlights) ? (data.highlights as string[]) : [];
      return {
        title,
        subtitle: join([text(data.title), text(data.location), period(data)]),
        detail: highlights[0] ?? "",
      };
    }
    case "project": {
      const tech = Array.isArray(data.technologies) ? (data.technologies as string[]).join(", ") : "";
      return { title, subtitle: join([tech, period(data)]), detail: text(data.description) };
    }
    case "certification":
      return { title, subtitle: join([text(data.issuer), text(data.date)]), detail: "" };
    case "achievement":
      return { title, subtitle: text(data.date), detail: text(data.description) };
    case "skill":
      return { title, subtitle: text(data.category), detail: "" };
    case "link":
      return { title, subtitle: text(data.label), detail: "" };
    default:
      return { title, subtitle: "", detail: "" };
  }
}

export function provenanceLabel(entry: ProfileEntry): string {
  return entry.source === "resume" && !entry.user_edited ? "From your resume" : "Added or edited by you";
}

export function flagLabels(entry: ProfileEntry, spec: EntrySpec | undefined): string[] {
  return entry.flags.map((name) => spec?.fields.find((f) => f.name === name)?.label ?? name);
}
