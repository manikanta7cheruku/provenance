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
