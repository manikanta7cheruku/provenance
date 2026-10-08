export interface PlannedScreen {
  title: string;
  description: string;
  why: string;
  next: string;
}

/** Copy for screens that later checkpoints build. Each entry is deleted when its screen ships. */
export const PLANNED_SCREENS: Record<string, PlannedScreen> = {
  "/opportunities": {
    title: "Opportunities",
    description: "Your ranked work queue of jobs, with the reasons behind every ranking.",
    why: "This is where you decide which jobs deserve your time. It needs a profile and analyzed jobs.",
    next: "Profile arrives in checkpoint 1.5 and job analysis in 1.6. The full workbench follows in Phase 2.",
  },
  "/saved": {
    title: "Saved",
    description: "Jobs you kept for later.",
    why: "A short list keeps you from re-reading postings you already considered.",
    next: "Saving jobs arrives with the workbench in Phase 2.",
  },
  "/applications": {
    title: "Applications",
    description: "A record of the jobs you applied to, applied by you on the employer's site.",
    why: "Provenance never submits applications. This list is your own tracking record.",
    next: "Application tracking arrives with the workbench in Phase 2.",
  },
  "/profile": {
    title: "Profile",
    description: "Your evidence base: resume, projects, skills and anything else you add.",
    why: "Every conclusion about a job is traced back to evidence stored here.",
    next: "Resume upload and the editable profile arrive in checkpoint 1.5. Sign-in comes first, in 1.2.",
  },
  "/runs": {
    title: "Runs",
    description: "A history of analysis runs and what each one did.",
    why: "Runs let you see what happened, how long it took and what evidence was used.",
    next: "Run tracking starts in checkpoint 1.4. The full inspector arrives in Phase 3.",
  },
};
