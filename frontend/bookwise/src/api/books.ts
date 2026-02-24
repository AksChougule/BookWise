import { requestJson } from "./client";
import { endpoints } from "./endpoints";

export type Book = {
  id: string;
  title: string;
  authors: string[];
  description: string | null;
  subjects: string[];
  cover_url: string | null;
  openlibrary_url: string;
  resolved_from: string;
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
  cache_key?: Record<string, string>;
};

export function getBook(workId: string): Promise<Book> {
  return requestJson<Book>(endpoints.book(workId));
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
