import type { SearchBook } from "../api/search";
import { BookCard } from "./BookCard";

type SearchResultsProps = {
  query: string;
  loading: boolean;
  error: string | null;
  results: SearchBook[];
  onRetry: () => void;
};

export function SearchResults({ query, loading, error, results, onRetry }: SearchResultsProps) {
  if (query.trim().length === 0) {
    return (
      <section className="rounded-xl border border-app bg-surface p-4">
        <p className="text-secondary">Search for an English book to get started.</p>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="rounded-xl border border-app bg-surface p-4">
        <p className="text-secondary">Searching...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border border-app bg-surface p-4">
        <p className="mb-2 text-sm text-red-700">{error}</p>
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      </section>
    );
  }

  if (results.length === 0) {
    return (
      <section className="rounded-xl border border-app bg-surface p-4">
        <p className="text-secondary">No results found.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-app bg-surface p-3">
      <div className="space-y-2 overflow-y-auto pr-1" style={{ maxHeight: "60vh" }}>
        {results.map((book) => (
          <BookCard key={book.id} book={book} />
        ))}
      </div>
    </section>
  );
}
