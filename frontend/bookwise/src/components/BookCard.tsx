import { useNavigate } from "react-router-dom";

import type { SearchBook } from "../api/search";
import { normalizeWorkId } from "../api/endpoints";

type BookCardProps = {
  book: SearchBook;
};

export function BookCard({ book }: BookCardProps) {
  const navigate = useNavigate();

  const workId = normalizeWorkId(book.id);
  const authorText = book.authors.length > 0 ? book.authors.join(", ") : "Unknown author";

  const openBook = () => {
    if (!workId) {
      return;
    }
    navigate(`/book/${workId}`);
  };

  return (
    <button
      type="button"
      onClick={openBook}
      className="w-full rounded-lg border border-app bg-surface p-3 text-left transition hover:bg-muted focus-visible:ring"
      disabled={!workId}
      aria-label={workId ? `Open ${book.title}` : `Unavailable work id for ${book.title}`}
    >
      <div className="flex items-start gap-3">
        {book.cover_url ? (
          <img
            src={book.cover_url}
            alt="Book cover"
            className="h-16 w-12 rounded border border-app object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-16 w-12 items-center justify-center rounded border border-app bg-muted text-xs text-secondary">
            No cover
          </div>
        )}
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-primary">{book.title}</h3>
          <p className="mt-1 text-sm text-secondary">{authorText}</p>
          {book.first_publish_year ? (
            <p className="mt-1 text-xs text-secondary">First published: {book.first_publish_year}</p>
          ) : null}
        </div>
      </div>
    </button>
  );
}
