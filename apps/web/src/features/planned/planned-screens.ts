export interface PlannedScreen {
  title: string;
  description: string;
  why: string;
  next: string;
}

/** Copy for screens that later checkpoints build. Each entry is deleted when its screen ships. */
export const PLANNED_SCREENS: Record<string, PlannedScreen> = {
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
};
