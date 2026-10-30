import { request } from "./api";

export interface FieldSpec {
  name: string;
  label: string;
  /** text, longtext, date, url or list */
  kind: string;
  max_length: number;
  required: boolean;
  recommended: boolean;
  hint: string;
}

export interface EntrySpec {
  entry_type: string;
  label: string;
  plural: string;
  primary_field: string;
  fields: FieldSpec[];
}

export type EntryData = Record<string, unknown>;

export interface ProfileEntry {
  id: string;
  entry_type: string;
  data: EntryData;
  user_edited: boolean;
  /** "resume" when a parse created it, "user" when the person added it. */
  source: "resume" | "user";
  /** Recommended fields still empty. */
  flags: string[];
  created_at: string;
  updated_at: string;
}

export interface Preferences {
  target_roles: string[];
  authorized_countries: string[];
  needs_sponsorship: boolean | null;
  locations: string[];
  open_to_relocate: boolean | null;
  remote_preference: "remote" | "hybrid" | "onsite" | "any" | null;
  employment_types: string[];
  min_salary_amount: number | null;
  min_salary_currency: string | null;
  exclusions: string[];
}

const BASE = "/api/v1/profile";

export function fetchEntrySpecs(signal?: AbortSignal): Promise<EntrySpec[]> {
  return request<EntrySpec[]>("GET", `${BASE}/schema`, { signal });
}

export function fetchEntries(signal?: AbortSignal): Promise<ProfileEntry[]> {
  return request<ProfileEntry[]>("GET", `${BASE}/entries`, { signal });
}

export function createEntry(entryType: string, data: EntryData): Promise<ProfileEntry> {
  return request<ProfileEntry>("POST", `${BASE}/entries`, { body: { entry_type: entryType, data } });
}

export function updateEntry(id: string, data: EntryData): Promise<ProfileEntry> {
  return request<ProfileEntry>("PATCH", `${BASE}/entries/${encodeURIComponent(id)}`, { body: { data } });
}

export function deleteEntry(id: string): Promise<void> {
  return request<void>("DELETE", `${BASE}/entries/${encodeURIComponent(id)}`);
}

export function fetchPreferences(signal?: AbortSignal): Promise<Preferences> {
  return request<Preferences>("GET", `${BASE}/preferences`, { signal });
}

export function savePreferences(preferences: Preferences): Promise<Preferences> {
  return request<Preferences>("PUT", `${BASE}/preferences`, { body: preferences });
}
