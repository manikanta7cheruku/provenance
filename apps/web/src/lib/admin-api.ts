import { request } from "./api";
import type { MessageResponse } from "./api";

export interface AdminUser {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  last_seen_at: string | null;
  active_sessions: number;
  profile_entries_count: number;
  runs_count: number;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditEvent {
  id: string;
  category: string;
  action: string;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  created_at: string;
  details: Record<string, unknown>;
}

export interface AdminUserDetail {
  user: AdminUser;
  recent_events: AuditEvent[];
}

export interface AuditList {
  items: AuditEvent[];
  next_before: string | null;
}

export interface Invite {
  id: string;
  email: string | null;
  status: "active" | "used" | "revoked" | "expired";
  created_at: string;
  expires_at: string;
  used_at: string | null;
  revoked_at: string | null;
  created_by_email: string | null;
}

export interface InviteCreated {
  invite: Invite;
  code: string;
}

export interface AdminOverview {
  users: number;
  verified_users: number;
  active_sessions: number;
}

export interface Worker {
  worker_id: string;
  hostname: string;
  started_at: string;
  last_seen_at: string;
  tasks_processed: number;
  status: "alive" | "stale";
}

export interface DeadLetter {
  id: string;
  task_type: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  finished_at: string | null;
  requeueable: boolean;
}

export interface AiModelUsage {
  provider: string;
  model: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface SystemOverview {
  queue: { by_state: Record<string, number>; oldest_waiting_seconds: number | null };
  workers: Worker[];
  dead_letters: DeadLetter[];
  ai_usage_24h: {
    calls: number;
    errors: number;
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number;
    by_model: AiModelUsage[];
  };
}

export interface UserFilters {
  q: string;
  role: "" | "USER" | "ADMIN";
  status: "" | "active" | "disabled";
  verified: "" | "true" | "false";
}

export type UserAction =
  | "disable"
  | "enable"
  | "revoke-sessions"
  | "promote"
  | "demote"
  | "resend-verification"
  | "send-password-reset";

const BASE = "/api/v1/admin";

export function fetchOverview(signal?: AbortSignal): Promise<AdminOverview> {
  return request<AdminOverview>("GET", `${BASE}/overview`, { signal });
}

export function fetchSystem(signal?: AbortSignal): Promise<SystemOverview> {
  return request<SystemOverview>("GET", `${BASE}/system`, { signal });
}

export function requeueTask(taskId: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/tasks/${encodeURIComponent(taskId)}/requeue`);
}

export function fetchUsers(filters: UserFilters, offset: number, signal?: AbortSignal): Promise<AdminUserList> {
  const params = new URLSearchParams({ limit: "25", offset: String(offset) });
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.role) params.set("role", filters.role);
  if (filters.status) params.set("status", filters.status);
  if (filters.verified) params.set("verified", filters.verified);
  return request<AdminUserList>("GET", `${BASE}/users?${params.toString()}`, { signal });
}

export function fetchUser(id: string, signal?: AbortSignal): Promise<AdminUserDetail> {
  return request<AdminUserDetail>("GET", `${BASE}/users/${encodeURIComponent(id)}`, { signal });
}

export function runUserAction(id: string, action: UserAction): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/users/${encodeURIComponent(id)}/${action}`);
}

export function fetchInvites(signal?: AbortSignal): Promise<Invite[]> {
  return request<Invite[]>("GET", `${BASE}/invites`, { signal });
}

export function createInvite(email: string, days: number): Promise<InviteCreated> {
  const body: { days: number; email?: string } = { days };
  if (email.trim()) body.email = email.trim();
  return request<InviteCreated>("POST", `${BASE}/invites`, { body });
}

export function revokeInvite(id: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/invites/${encodeURIComponent(id)}/revoke`);
}

export function fetchAudit(
  filters: { category: "" | "audit" | "security"; action: string },
  before: string | null,
  signal?: AbortSignal,
): Promise<AuditList> {
  const params = new URLSearchParams({ limit: "50" });
  if (filters.category) params.set("category", filters.category);
  if (filters.action.trim()) params.set("action", filters.action.trim());
  if (before) params.set("before", before);
  return request<AuditList>("GET", `${BASE}/audit?${params.toString()}`, { signal });
}
