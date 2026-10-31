/**
 * The state vocabulary shared with the backend.
 * The backend decides the state (ui_state in every response). The frontend only renders it.
 * `npm run check:states` fails CI if this list differs from packages/domain/src/pv_domain/states.py.
 */
export const UI_STATES = [
  "queued",
  "processing",
  "waiting_for_you",
  "retrying",
  "completed",
  "retry_available",
  "permanently_failed",
  "cancelled",
] as const;

export type UiState = (typeof UI_STATES)[number];
export type StateTone = "ok" | "warn" | "danger" | "neutral";

export interface StateDescription {
  label: string;
  tone: StateTone;
  /** One plain sentence: what is happening and whether the user needs to do anything. */
  explanation: string;
}

const INFO: Record<UiState, StateDescription> = {
  queued: {
    label: "Queued",
    tone: "neutral",
    explanation: "Waiting for its turn. Nothing is needed from you.",
  },
  processing: {
    label: "Processing",
    tone: "neutral",
    explanation: "Working on it now. You can leave this page; it keeps going.",
  },
  waiting_for_you: {
    label: "Waiting for you",
    tone: "warn",
    explanation: "It needs an answer from you before it can continue.",
  },
  retrying: {
    label: "Retrying",
    tone: "warn",
    explanation: "Something went wrong for a moment. It will try again by itself.",
  },
  completed: {
    label: "Completed",
    tone: "ok",
    explanation: "Finished successfully.",
  },
  retry_available: {
    label: "Failed, retry available",
    tone: "danger",
    explanation: "It stopped, and trying again may work.",
  },
  permanently_failed: {
    label: "Failed",
    tone: "danger",
    explanation: "It stopped and trying again will not help. Your data is unchanged.",
  },
  cancelled: {
    label: "Cancelled",
    tone: "neutral",
    explanation: "It was stopped before it finished.",
  },
};

export function describeState(state: UiState): StateDescription {
  return INFO[state];
}

/** States in which a run is still moving, so the screen should keep refreshing. */
export function isActiveState(state: UiState): boolean {
  return state === "queued" || state === "processing" || state === "retrying";
}

/** What the user sees for an uploaded resume. The browser adds Idle and Uploading itself. */
export const RESUME_UI_STATES = [
  "uploaded",
  "parsing",
  "parsed",
  "needs_correction",
  "confirmed",
  "failed",
] as const;

export type ResumeUiState = (typeof RESUME_UI_STATES)[number];

export interface ResumeStateDescription {
  label: string;
  tone: StateTone;
  explanation: string;
}

const RESUME_INFO: Record<ResumeUiState, ResumeStateDescription> = {
  uploaded: {
    label: "Uploaded",
    tone: "neutral",
    explanation: "Your file is stored. Reading it starts in a moment.",
  },
  parsing: {
    label: "Reading your resume",
    tone: "neutral",
    explanation: "We are turning it into editable entries. You can leave this page; it keeps going.",
  },
  parsed: {
    label: "Ready to review",
    tone: "warn",
    explanation: "Check the entries below, fix anything that is wrong, then confirm.",
  },
  needs_correction: {
    label: "Needs correction",
    tone: "warn",
    explanation: "Some entries are missing details that help your matches. Add them, or confirm anyway.",
  },
  confirmed: {
    label: "Confirmed",
    tone: "ok",
    explanation: "You have reviewed your profile. It is ready for job analysis.",
  },
  failed: {
    label: "Could not read it",
    tone: "danger",
    explanation: "Your file is safe. See below for what to do next.",
  },
};

export function describeResumeState(state: ResumeUiState): ResumeStateDescription {
  return RESUME_INFO[state];
}

/** Uploaded and parsing change by themselves, so the page keeps asking until they settle. */
export function isResumeBusy(state: ResumeUiState): boolean {
  return state === "uploaded" || state === "parsing";
}

/** What the user sees for a pasted job posting. */
export const JOB_UI_STATES = ["reading", "ready", "failed"] as const;

export type JobUiState = (typeof JOB_UI_STATES)[number];

const JOB_INFO: Record<JobUiState, ResumeStateDescription> = {
  reading: {
    label: "Reading the posting",
    tone: "neutral",
    explanation: "We are finding what it asks for. You can leave this page; it keeps going.",
  },
  ready: {
    label: "Ready",
    tone: "ok",
    explanation: "Here is what the posting asks for, and whether anything stands in your way.",
  },
  failed: {
    label: "Could not read it",
    tone: "danger",
    explanation: "Your posting is saved. See below for what to do next.",
  },
};

export function describeJobState(state: JobUiState): ResumeStateDescription {
  return JOB_INFO[state];
}

export function isJobBusy(state: JobUiState): boolean {
  return state === "reading";
}

export const ELIGIBILITY_STATES = [
  "eligible",
  "not_eligible",
  "uncertain",
  "requires_user_input",
] as const;

export type EligibilityState = (typeof ELIGIBILITY_STATES)[number];

const ELIGIBILITY_INFO: Record<EligibilityState, { label: string; tone: StateTone }> = {
  eligible: { label: "Nothing in the way", tone: "ok" },
  not_eligible: { label: "Blocked", tone: "danger" },
  uncertain: { label: "Worth a closer look", tone: "warn" },
  requires_user_input: { label: "Needs your answer", tone: "warn" },
};

export function describeEligibility(state: EligibilityState): { label: string; tone: StateTone } {
  return ELIGIBILITY_INFO[state];
}


/** The evidence check of a job: what the person sees while and after it runs. */
export const ANALYSIS_UI_STATES = [
  "not_started",
  "working",
  "needs_answer",
  "ready",
  "failed",
] as const;

export type AnalysisUiState = (typeof ANALYSIS_UI_STATES)[number];

const ANALYSIS_INFO: Record<AnalysisUiState, ResumeStateDescription> = {
  not_started: {
    label: "Not checked yet",
    tone: "neutral",
    explanation: "Check what you can prove for each requirement, using only your own profile.",
  },
  working: {
    label: "Checking your evidence",
    tone: "neutral",
    explanation: "Results appear as they are found. You can leave this page; it keeps going.",
  },
  needs_answer: {
    label: "A question for you",
    tone: "warn",
    explanation: "Some evidence cannot be found in your profile. A short answer can settle it.",
  },
  ready: {
    label: "Checked",
    tone: "ok",
    explanation: "Every requirement now has a verdict and the evidence behind it.",
  },
  failed: {
    label: "Stopped early",
    tone: "danger",
    explanation: "What was found so far is saved.",
  },
};

export function describeAnalysisState(state: AnalysisUiState): ResumeStateDescription {
  return ANALYSIS_INFO[state];
}

export function isAnalysisBusy(state: AnalysisUiState): boolean {
  return state === "working";
}

/** The verdict on one requirement. Not verified means no proof was found, not that it is missing. */
export const VERDICTS = ["met", "partial", "not_verified", "conflicting"] as const;

export type Verdict = (typeof VERDICTS)[number];

const VERDICT_INFO: Record<Verdict, { label: string; tone: StateTone }> = {
  met: { label: "Met", tone: "ok" },
  partial: { label: "Partly met", tone: "warn" },
  not_verified: { label: "Not verified", tone: "neutral" },
  conflicting: { label: "Conflicting", tone: "danger" },
};

export function describeVerdict(verdict: Verdict): { label: string; tone: StateTone } {
  return VERDICT_INFO[verdict];
}

export const BANDS = ["strong", "good", "review", "not_recommended", "not_eligible"] as const;

export type Band = (typeof BANDS)[number];

const BAND_INFO: Record<Band, { label: string; tone: StateTone }> = {
  strong: { label: "Strong match", tone: "ok" },
  good: { label: "Good match", tone: "ok" },
  review: { label: "Worth a review", tone: "warn" },
  not_recommended: { label: "Not recommended", tone: "neutral" },
  not_eligible: { label: "Not eligible", tone: "danger" },
};

export function describeBand(band: Band): { label: string; tone: StateTone } {
  return BAND_INFO[band];
}
