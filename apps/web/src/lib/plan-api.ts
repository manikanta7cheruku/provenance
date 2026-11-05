import { request } from "./api";

export interface Quota {
  unit: string;
  label: string;
  noun: string;
  help: string;
  used: number;
  /** null means no limit. */
  limit: number | null;
  remaining: number | null;
  percent: number;
  state: "ok" | "near" | "reached";
}

export interface PlanChoice {
  id: string;
  label: string;
  current: boolean;
  limits: Record<string, number | null>;
  resumes: number;
  exports_per_resume: number;
}

export interface PlanState {
  plan_id: string;
  plan_label: string;
  period_start: string;
  resets_at: string;
  quotas: Quota[];
  resumes_used: number;
  resumes_limit: number;
  exports_per_resume: number;
  plans: PlanChoice[];
  recent: { label: string; amount: number; at: string }[];
  payments: { enabled: boolean; message: string };
  provisional: boolean;
}

export function fetchPlan(signal?: AbortSignal): Promise<PlanState> {
  return request<PlanState>("GET", "/api/v1/plan", { signal });
}

/** How a meter is described in words, so it never depends on its color or its length. */
export function describeQuota(quota: Quota): string {
  if (quota.limit === null) return `${quota.used} used, no limit on your plan`;
  if (quota.state === "reached")
    return quota.limit === 0
      ? "Not included in your plan"
      : `${quota.used} of ${quota.limit} used. The limit is reached`;
  if (quota.state === "near")
    return `${quota.used} of ${quota.limit} used. Nearly at the limit`;
  return `${quota.used} of ${quota.limit} used`;
}

/** A day such as "1 December", read in UTC because the month rolls over in UTC. */
export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  });
}

export function limitWords(limit: number | null | undefined): string {
  return limit === null || limit === undefined ? "No limit" : String(limit);
}
