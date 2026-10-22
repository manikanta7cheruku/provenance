/** Display helpers. They never throw on bad input: a screen should not break on a odd value. */

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "Not finished";
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

export function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "None waiting";
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

export function formatCost(usd: number): string {
  return usd === 0 ? "$0 (no prices configured, or free tier)" : `$${usd.toFixed(4)}`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString();
}
