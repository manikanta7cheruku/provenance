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
