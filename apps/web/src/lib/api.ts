export interface ApiStatus {
  service: string;
  version: string;
  environment: string;
  ready: boolean;
  checks: {
    database: "ok" | "fail";
    migrations: "ok" | "behind" | "unknown";
  };
}

export interface AuthConfig {
  signup_mode: "invite" | "open";
  email_verification_required: boolean;
}

export interface SessionUser {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  email_verified: boolean;
}

export interface SessionResponse {
  authenticated: boolean;
  user: SessionUser | null;
  csrf_token: string | null;
  config: AuthConfig;
}

export interface MessageResponse {
  message: string;
}

/** Every API failure arrives in one shape. This class carries it to the UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    code: string,
    message: string,
    fields: Record<string, string> = {},
    retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

interface ErrorBody {
  code?: string;
  message?: string;
  fields?: Record<string, string>;
  retry_after_seconds?: number;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

let csrfToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

/** The session provider registers a handler that runs when the server says the session ended. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export async function request<T>(
  method: Method,
  path: string,
  options: { body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Could not reach the server. Check your connection and try again.",
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const body = (data ?? {}) as ErrorBody;
    const error = new ApiError(
      response.status,
      body.code ?? "UNKNOWN_ERROR",
      body.message ?? `The server answered with HTTP ${response.status}.`,
      body.fields ?? {},
      body.retry_after_seconds ?? null,
    );
    if (response.status === 401 && error.code === "UNAUTHENTICATED") onUnauthorized?.();
    throw error;
  }
  return data as T;
}

export function fetchStatus(signal?: AbortSignal): Promise<ApiStatus> {
  return request<ApiStatus>("GET", "/api/v1/status", { signal });
}
