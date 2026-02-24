import { requestJson } from "./client";
import { endpoints } from "./endpoints";

export type SearchBook = {
  id: string;
  title: string;
  authors: string[];
  first_publish_year: number | null;
  language: string[];
  cover_url: string | null;
};

export type SearchResult = {
  query: string;
  results: SearchBook[];
};

export function searchBooks(q: string, signal?: AbortSignal): Promise<SearchResult> {
  const params = new URLSearchParams({ q });
  return requestJson<SearchResult>(`${endpoints.search}?${params.toString()}`, { signal });
}
