import { normalizeWorkId } from "./endpoints";
import { ApiError, requestJson, requestJsonWithMeta } from "./client";
import { endpoints } from "./endpoints";

export type RawBook = {
  id?: unknown;
  work_id?: unknown;
  key?: unknown;
  title?: unknown;
  authors?: unknown;
  author_name?: unknown;
  description?: unknown;
  subjects?: unknown;
  cover_url?: unknown;
  openlibrary_url?: unknown;
  first_publish_year?: unknown;
  resolved_from?: unknown;
};

export type Book = RawBook;

export type BookViewModel = {
  id: string;
  title: string;
  authors: string[];
  description: string | null;
  cover_url: string | null;
  subjects: string[];
  first_publish_year: number | null;
  source_urls: {
    openlibrary?: string;
  };
};

export type GenerationSection = "overview" | "key_ideas" | "chapters" | "critique";

export type GenerationResponse = {
  book_id: string;
  section: GenerationSection;
  prompt_version: string;
  provider: string;
  model: string;
  stored: boolean;
  status?: "complete";
  content: Record<string, unknown> | null;
};

export type GenerationPendingResponse = {
  stored: false;
  in_progress: true;
  retry_after_ms: number;
  status?: "pending";
  cache_key?: Record<string, string>;
};

export type GenerationStatusResponse =
  | {
      status: "missing";
      retry_after_ms?: null;
    }
  | {
      status: "pending";
      in_progress: true;
      retry_after_ms: number;
    }
  | {
      status: "complete";
      stored: true;
      updated_at: string | null;
      retry_after_ms: null;
    }
  | {
      status: "failed";
      error_code?: string | null;
      retry_after_ms: null;
    };

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter((item) => item.trim().length > 0);
}

function normalizeDescription(value: unknown): string | null {
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
  }
  if (value && typeof value === "object" && "value" in value) {
    const nested = (value as { value?: unknown }).value;
    if (typeof nested === "string") {
      const normalized = nested.trim();
      return normalized.length > 0 ? normalized : null;
    }
  }
  return null;
}

function normalizeYear(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value.slice(0, 4), 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function normalizeBook(raw: Book, fallbackWorkId?: string): BookViewModel {
  const id =
    normalizeWorkId(raw.id) ??
    normalizeWorkId(raw.work_id) ??
    normalizeWorkId(raw.key) ??
    normalizeWorkId(fallbackWorkId) ??
    "unknown";

  const title = typeof raw.title === "string" && raw.title.trim().length > 0 ? raw.title : "Untitled";
  const authors = toStringArray(raw.authors ?? raw.author_name);

  const subjects = toStringArray(raw.subjects).slice(0, 8);
  const cover_url = typeof raw.cover_url === "string" && raw.cover_url.length > 0 ? raw.cover_url : null;
  const openlibrary =
    typeof raw.openlibrary_url === "string" && raw.openlibrary_url.length > 0
      ? raw.openlibrary_url
      : `https://openlibrary.org/works/${id}`;

  return {
    id,
    title,
    authors,
    description: normalizeDescription(raw.description),
    cover_url,
    subjects,
    first_publish_year: normalizeYear(raw.first_publish_year),
    source_urls: {
      openlibrary,
    },
  };
}

export function getBook(workId: string, signal?: AbortSignal): Promise<Book> {
  return requestJson<Book>(endpoints.book(workId), { signal });
}

export function generateSection(
  workId: string,
  section: GenerationSection,
  opts: { force?: boolean } = {},
): Promise<GenerationResponse | GenerationPendingResponse> {
  const params = new URLSearchParams();
  if (opts.force) {
    params.set("force", "true");
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return requestJson<GenerationResponse | GenerationPendingResponse>(
    `${endpoints.generateSection(workId, section)}${suffix}`,
    { method: "POST" },
  );
}

function parseRetryAfterToMs(headers: Headers): number | null {
  const headerValue = headers.get("Retry-After");
  if (!headerValue) {
    return null;
  }
  const seconds = Number.parseInt(headerValue, 10);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return null;
  }
  return seconds * 1000;
}

export async function getGenerationStatus(
  workId: string,
  section: GenerationSection,
): Promise<GenerationStatusResponse> {
  let response: Awaited<ReturnType<typeof requestJsonWithMeta<GenerationStatusResponse>>>;
  try {
    response = await requestJsonWithMeta<GenerationStatusResponse>(
      endpoints.generationStatus(workId, section),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      const bodyStatus =
        error.body && typeof error.body === "object" ? (error.body as { status?: unknown }).status : null;
      const detailStatus =
        error.body && typeof error.body === "object"
          ? ((error.body as { detail?: unknown }).detail as { status?: unknown } | undefined)?.status
          : null;
      if (bodyStatus === "missing" || detailStatus === "missing") {
        return { status: "missing", retry_after_ms: null };
      }
    }
    throw error;
  }

  const retryAfterMsFromHeader = parseRetryAfterToMs(response.headers);
  if (response.data.status === "pending") {
    return {
      ...response.data,
      retry_after_ms: Math.max(
        response.data.retry_after_ms,
        retryAfterMsFromHeader ?? 0,
      ),
    };
  }
  return response.data;
}
