import { request } from "./api";

export interface GitHubRepo {
  id: number;
  full_name: string;
  name: string;
  description: string;
  language: string;
  topics: string[];
  stars: number;
  fork: boolean;
  archived: boolean;
  url: string;
  selected: boolean;
  suggested: boolean;
  has_excerpt: boolean;
}

export interface Platform {
  name: string;
  why: string;
  what: string;
}

export type SyncState = "idle" | "queued" | "syncing" | "failed";

export interface GitHubState {
  /** Whether GitHub is set up on this server at all. */
  available: boolean;
  connected: boolean;
  login: string | null;
  profile_url: string | null;
  /** The permission asked of GitHub. Empty means none: public information only. */
  scope: string;
  scope_sentence: string;
  sync_state: SyncState;
  sync_error: string | null;
  connected_at: string | null;
  last_synced_at: string | null;
  repos: GitHubRepo[];
  max_selected: number;
  entries_from_github: number;
  platforms: Platform[];
}

const BASE = "/api/v1/github";

export function fetchGitHub(signal?: AbortSignal): Promise<GitHubState> {
  return request<GitHubState>("GET", BASE, { signal });
}

export function startGitHub(): Promise<{ authorize_url: string }> {
  return request<{ authorize_url: string }>("POST", `${BASE}/start`);
}

export function finishGitHub(code: string, state: string): Promise<{ login: string }> {
  return request<{ login: string }>("POST", `${BASE}/callback`, { body: { code, state } });
}

export function syncGitHub(): Promise<void> {
  return request<void>("POST", `${BASE}/sync`);
}

export function chooseRepos(repoIds: number[]): Promise<void> {
  return request<void>("PUT", `${BASE}/repos`, { body: { repo_ids: repoIds } });
}

export function disconnectGitHub(keepEntries: boolean): Promise<{ revoked: boolean; entries_removed: number }> {
  return request<{ revoked: boolean; entries_removed: number }>("POST", `${BASE}/disconnect`, { body: { keep_entries: keepEntries } });
}

/** Whether a read of the repositories is still going on, so the screen keeps looking. */
export function isSyncing(state: SyncState): boolean {
  return state === "queued" || state === "syncing";
}
