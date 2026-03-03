import { useMemo, useState } from "react";

import type { BookViewModel } from "../api/books";

type BookHeaderProps = {
  book: BookViewModel;
};

const COLLAPSED_MAX_HEIGHT = 220;

export function BookHeader({ book }: BookHeaderProps) {
  const [expanded, setExpanded] = useState(false);

  const description = book.description ?? "No description available.";
  const authorsText = book.authors.length > 0 ? book.authors.join(", ") : "Unknown author";
  const hasLongDescription = description.length > 600;

  const descriptionStyle = useMemo(
    () =>
      expanded
        ? { whiteSpace: "pre-wrap" as const }
        : {
            whiteSpace: "pre-wrap" as const,
            maxHeight: `${COLLAPSED_MAX_HEIGHT}px`,
            overflow: "hidden",
          },
    [expanded],
  );

  return (
    <section className="rounded-xl border border-app bg-surface p-6">
      <div className="book-header-layout">
        <div>
          {book.cover_url ? (
            <img
              src={book.cover_url}
              alt={`Cover of ${book.title}`}
              className="book-cover"
              loading="lazy"
            />
          ) : (
            <div className="book-cover-placeholder">
              <span>No cover</span>
            </div>
          )}
        </div>

        <div className="space-y-3 min-w-0">
          <h1 className="text-2xl font-semibold">{book.title}</h1>
          <p className="text-secondary">{authorsText}</p>

          <div className="book-meta-row text-sm text-secondary">
            <span>Work ID: {book.id}</span>
            {book.first_publish_year ? <span>First published: {book.first_publish_year}</span> : null}
            {book.source_urls.openlibrary ? (
              <a
                href={book.source_urls.openlibrary}
                target="_blank"
                rel="noreferrer"
                className="book-link"
              >
                Open Library
              </a>
            ) : null}
          </div>

          <div>
            <h2 className="text-sm font-medium text-secondary">Description</h2>
            <p className="mt-1 text-primary" style={descriptionStyle}>
              {description}
            </p>
            {hasLongDescription ? (
              <button type="button" className="btn mt-2" onClick={() => setExpanded((value) => !value)}>
                {expanded ? "Read less" : "Read more"}
              </button>
            ) : null}
          </div>

          {book.subjects.length > 0 ? (
            <div>
              <h2 className="text-sm font-medium text-secondary">Subjects</h2>
              <div className="book-tags mt-2">
                {book.subjects.map((subject) => (
                  <span key={subject} className="book-tag">
                    {subject}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
