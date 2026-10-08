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

export async function fetchStatus(signal?: AbortSignal): Promise<ApiStatus> {
  const response = await fetch("/api/v1/status", {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`The API answered with HTTP ${response.status}.`);
  }
  return (await response.json()) as ApiStatus;
}
