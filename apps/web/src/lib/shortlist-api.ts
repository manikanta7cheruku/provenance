import { request } from "./api";

export type Frequency = "daily" | "weekly";

export interface ShortlistSettings {
  enabled: boolean;
  frequency: Frequency;
  weekday: number;
  hour: number;
  timezone: string;
  max_items: number;
  schedule_text: string;
  next_run_at: string | null;
  last_run_at: string | null;
}

export interface ShortlistRun {
  outcome: "sent" | "nothing" | "skipped" | "failed";
  outcome_text: string;
  item_count: number;
  manual: boolean;
  at: string;
}

export interface Shortlist {
  settings: ShortlistSettings;
  runs: ShortlistRun[];
  email_verified: boolean;
  /** Why the email cannot be turned on yet, when it cannot. */
  blocker: string | null;
  delivery_note: string;
}

export interface ShortlistItem {
  id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  band: string | null;
  eligibility: string | null;
  reason: string;
}

export interface ShortlistPreview {
  items: ShortlistItem[];
  note: string;
}

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

export function fetchShortlist(signal?: AbortSignal): Promise<Shortlist> {
  return request<Shortlist>("GET", "/api/v1/shortlist", { signal });
}

export function saveShortlist(settings: Omit<ShortlistSettings, "schedule_text" | "next_run_at" | "last_run_at">): Promise<Shortlist> {
  return request<Shortlist>("PUT", "/api/v1/shortlist", { body: settings });
}

export function fetchPreview(signal?: AbortSignal): Promise<ShortlistPreview> {
  return request<ShortlistPreview>("GET", "/api/v1/shortlist/preview", { signal });
}

export function sendShortlistNow(): Promise<{ queued: boolean; message: string }> {
  return request<{ queued: boolean; message: string }>("POST", "/api/v1/shortlist/send");
}

/** The time zones the browser knows, with the person's own first. Falls back to a short list. */
export function timeZones(own: string): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  let zones: string[] = [];
  try {
    zones = intl.supportedValuesOf?.("timeZone") ?? [];
  } catch {
    zones = [];
  }
  if (zones.length === 0) zones = ["UTC", "Asia/Kolkata", "Europe/London", "America/New_York", "America/Los_Angeles"];
  return Array.from(new Set([own, "UTC", ...zones]));
}

export function ownTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}
