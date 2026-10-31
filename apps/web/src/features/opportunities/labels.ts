import type { JobFact, JobSummary } from "../../lib/jobs-api";

const WORK_MODE: Record<string, string> = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site" };
const EMPLOYMENT: Record<string, string> = {
  full_time: "Full time",
  part_time: "Part time",
  internship: "Internship",
  contract: "Contract",
  freelance: "Freelance",
};
const SENIORITY: Record<string, string> = {
  intern: "Intern",
  entry: "Entry level",
  mid: "Mid level",
  senior: "Senior",
  lead: "Lead",
};
const SPONSORSHIP: Record<string, string> = {
  offered: "Offers visa sponsorship",
  not_offered: "Does not sponsor visas",
};

export const FACT_LABELS: Record<string, string> = {
  location: "Place",
  work_mode: "Where the work happens",
  employment_type: "Kind of work",
  seniority: "Level",
  min_years_experience: "Years of experience asked for",
  sponsorship: "Visa sponsorship",
  work_authorization_countries: "Must already be allowed to work in",
};

export const CATEGORY_LABELS: Record<string, string> = {
  skill: "Skill",
  experience: "Experience",
  education: "Education",
  certification: "Certification",
  language: "Language",
  work_authorization: "Work authorization",
  location: "Location",
  other: "Other",
};

/** How the text reached us, said plainly. Never "searched": the person pasted it. */
export function acquisitionLabel(method: string): string {
  return method === "user_paste" ? "Pasted by you" : method;
}

export function workLine(job: Pick<JobSummary, "work_mode" | "location">): string {
  const mode = job.work_mode ? (WORK_MODE[job.work_mode] ?? job.work_mode) : "";
  return [mode, job.location ?? ""].filter(Boolean).join(" · ");
}

export function factText(key: string, fact: JobFact): string {
  const value = fact.value;
  if (Array.isArray(value)) return value.join(", ");
  const text = String(value);
  if (key === "work_mode") return WORK_MODE[text] ?? text;
  if (key === "employment_type") return EMPLOYMENT[text] ?? text;
  if (key === "seniority") return SENIORITY[text] ?? text;
  if (key === "sponsorship") return SPONSORSHIP[text] ?? text;
  if (key === "min_years_experience") return `${text} ${text === "1" ? "year" : "years"}`;
  return text;
}
