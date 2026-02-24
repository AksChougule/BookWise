export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export const endpoints = {
  healthRoot: "/health",
  healthApi: "/api/health",
  metrics: "/metrics",
  search: "/api/search",
  curatedRandom: "/api/curated/random",
  book: (workId: string) => `/api/books/${encodeURIComponent(workId)}`,
  generateSection: (workId: string, section: string) =>
    `/api/books/${encodeURIComponent(workId)}/generate/${encodeURIComponent(section)}`,
} as const;

export function normalizeWorkId(value: unknown): string | null {
  if (typeof value === "string") {
    if (/^OL\d+W$/.test(value)) {
      return value;
    }
    const match = value.match(/\/works\/(OL\d+W)$/);
    if (match?.[1]) {
      return match[1];
    }
    return null;
  }

  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    return (
      normalizeWorkId(record.work_id) ??
      normalizeWorkId(record.id) ??
      normalizeWorkId(record.key)
    );
  }

  return null;
}
