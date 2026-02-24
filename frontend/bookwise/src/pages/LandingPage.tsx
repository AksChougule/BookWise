import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { searchBooks, type SearchBook } from "../api/search";
import { QuoteBanner } from "../components/QuoteBanner";
import { SearchBox } from "../components/SearchBox";
import { SearchResults } from "../components/SearchResults";
import { SurpriseMeButton } from "../components/SurpriseMeButton";
import { useDebounce } from "../hooks/useDebounce";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 408) {
      return "Search request timed out. Please retry.";
    }
    return `Search failed (${error.status}). Please try again.`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error while searching.";
}

export default function LandingPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchBook[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedQuery = useDebounce(query, 300);
  const activeControllerRef = useRef<AbortController | null>(null);

  const trimmedDebouncedQuery = useMemo(() => debouncedQuery.trim(), [debouncedQuery]);

  const runSearch = useCallback(async (nextQuery: string) => {
    const trimmed = nextQuery.trim();

    activeControllerRef.current?.abort();
    activeControllerRef.current = null;

    if (trimmed.length === 0) {
      setResults([]);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    activeControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const payload = await searchBooks(trimmed, controller.signal);
      if (activeControllerRef.current !== controller) {
        return;
      }
      setResults(payload.results ?? []);
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      setResults([]);
      setError(toErrorMessage(err));
    } finally {
      if (activeControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void runSearch(trimmedDebouncedQuery);
  }, [trimmedDebouncedQuery, runSearch]);

  useEffect(
    () => () => {
      activeControllerRef.current?.abort();
    },
    [],
  );

  return (
    <section className="space-y-4">
      <QuoteBanner />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Discover your next book</h1>
        <SurpriseMeButton />
      </div>

      <SearchBox value={query} onChange={setQuery} onSubmit={() => void runSearch(query)} />

      <SearchResults
        query={query}
        loading={loading}
        error={error}
        results={results}
        onRetry={() => void runSearch(query)}
      />

      {/* Manual verification:
          - Search updates on typing pause
          - Clearing input clears results
          - Clicking result routes to /book/:workId
          - Surprise Me routes to /book/:workId
          - Dark mode styling works for banner/input/cards/scroll area
      */}
    </section>
  );
}
