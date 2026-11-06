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

// ---- checkpoint 3.5: health, cost, run trace, sources

export type Level = "ok" | "warning" | "critical" | "unknown";

export interface AdminAlert {
  key: string;
  severity: "critical" | "warning";
  title: string;
  detail: string;
  action: string;
  runbook: string;
}

export interface HealthComponent {
  name: string;
  status: Level;
  detail: string;
}

export interface TroubleTask {
  id: string;
  task_type: string;
  state: "retrying" | "stuck";
  attempts: number;
  max_attempts: number;
  run_id: string | null;
  last_error: string | null;
  run_after: string;
}

export interface SourceHealth {
  key: string;
  name: string;
  enabled: boolean;
  status: string;
  breaker_open: boolean;
  failure_streak: number;
  last_success_at: string | null;
  last_failure_at: string | null;
}

export interface Health {
  status: "ok" | "warning" | "critical";
  headline: string;
  version: string;
  environment: string;
  generated_at: string;
  components: HealthComponent[];
  alerts: AdminAlert[];
  requests: {
    measured: boolean;
    window_minutes: number;
    requests: number;
    server_errors: number;
    client_errors: number;
    p50_ms: number | null;
    p95_ms: number | null;
  };
  queue_by_state: Record<string, number>;
  oldest_waiting_seconds: number | null;
  trouble_tasks: TroubleTask[];
  sources: SourceHealth[];
  security_24h: { action: string; label: string; count: number }[];
  rate_limits_24h: { policy: string; counters_over: number }[];
  thresholds: {
    queue_stale_warning_seconds: number;
    queue_stale_critical_seconds: number;
    source_failure_streak: number;
    llm_error_rate: number;
    daily_spend_ceiling_usd: number;
    server_error_rate: number;
    p95_ms: number;
    auth_failures_per_hour: number;
  };
}

export interface UsageRow {
  key: string;
  calls: number;
  errors: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface Usage {
  days: number;
  calls: number;
  errors: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  accounts: number;
  average_latency_ms: number | null;
  highest_account_share: number | null;
  daily_spend_ceiling_usd: number;
  by_model: UsageRow[];
  by_purpose: UsageRow[];
  by_day: UsageRow[];
  by_plan: UsageRow[];
}

export interface Trace {
  run_id: string;
  found: boolean;
  tasks: {
    id: string;
    task_type: string;
    state: string;
    attempts: number;
    max_attempts: number;
    last_error: string | null;
    created_at: string;
    finished_at: string | null;
    owner_email: string | null;
  }[];
  calls: {
    purpose: string;
    provider: string;
    model: string;
    prompt_version: string | null;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    latency_ms: number;
    status: string;
    error_class: string | null;
    created_at: string;
  }[];
}

export interface AdminSource {
  key: string;
  display_name: string;
  enabled: boolean;
  compliance_status: string;
  health_status: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  failure_streak: number;
  breaker_open_until: string | null;
  jobs_open: number;
  enable_blocker: string | null;
  review_expired: boolean;
}

export interface FetchLogRow {
  started_at: string;
  board_id: string | null;
  outcome: string;
  http_status: number | null;
  duration_ms: number;
  jobs_seen: number;
  jobs_new: number;
  jobs_changed: number;
  jobs_closed: number;
  jobs_skipped: number;
  error_class: string | null;
}

export function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return request<Health>("GET", `${BASE}/health`, { signal });
}

export function fetchUsage(days: 7 | 30, signal?: AbortSignal): Promise<Usage> {
  return request<Usage>("GET", `${BASE}/usage?days=${days}`, { signal });
}

export function fetchTrace(runId: string, signal?: AbortSignal): Promise<Trace> {
  return request<Trace>("GET", `${BASE}/trace/${encodeURIComponent(runId)}`, { signal });
}

export function fetchSources(signal?: AbortSignal): Promise<AdminSource[]> {
  return request<AdminSource[]>("GET", `${BASE}/sources`, { signal });
}

export function fetchSourceLog(key: string, signal?: AbortSignal): Promise<FetchLogRow[]> {
  return request<FetchLogRow[]>("GET", `${BASE}/sources/${encodeURIComponent(key)}/log`, { signal });
}

export function pollSource(key: string): Promise<MessageResponse> {
  return request<MessageResponse>("POST", `${BASE}/sources/${encodeURIComponent(key)}/poll`);
}

// ---- checkpoint 3.6: evaluation

export interface EvalRun {
  id: string;
  created_at: string;
  suite: "deterministic" | "llm";
  trigger: string;
  dataset_version: string;
  git_sha: string | null;
  model: string | null;
  passed: boolean;
  case_count: number;
  failure_count: number;
  regressions: string[];
}

export interface EvalMetric {
  name: string;
  label: string;
  suite: string;
  value: number;
  baseline: number | null;
  limit: number;
  direction: "higher" | "lower";
  status: "ok" | "regressed" | "below_limit" | "new";
  delta: number | null;
  cases: number;
  previous: number | null;
  change: number | null;
}

export interface EvalDetail {
  run: EvalRun;
  versions: Record<string, string>;
  metrics: EvalMetric[];
  suites: { name: string; cases: number; failed: number }[];
  failures: { suite: string; case_id: string; expected: string; got: string; note: string }[];
  against: EvalRun | null;
}

export interface Ranker {
  adopt: boolean;
  labels: number;
  people: number;
  reasons: string[];
}

export function fetchEvaluations(
  signal?: AbortSignal,
): Promise<{ runs: EvalRun[]; latest: Record<string, EvalRun>; ranker: Ranker }> {
  return request("GET", `${BASE}/evaluation`, { signal });
}

export function fetchEvaluation(id: string, against: string | null, signal?: AbortSignal): Promise<EvalDetail> {
  const query = against ? `?against=${encodeURIComponent(against)}` : "";
  return request<EvalDetail>("GET", `${BASE}/evaluation/${encodeURIComponent(id)}${query}`, { signal });
}
