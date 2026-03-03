import { useState } from "react";

import { StoredBadge } from "./StoredBadge";

type SectionCardProps = {
  title: string;
  status: "idle" | "loading" | "success" | "error";
  stored: boolean | null;
  error: string | null;
  onRegenerate: () => void;
  onRetry: () => void;
  collapsible?: boolean;
  defaultOpen?: boolean;
  hasContent?: boolean;
  children: React.ReactNode;
};

export function SectionCard({
  title,
  status,
  stored,
  error,
  onRegenerate,
  onRetry,
  collapsible = false,
  defaultOpen = true,
  hasContent = false,
  children,
}: SectionCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const loading = status === "loading";
  const isRegenerating = loading && hasContent;

  return (
    <section className="rounded-xl border border-app bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{title}</h2>
          <StoredBadge stored={stored} />
        </div>

        <div className="flex items-center gap-2">
          {collapsible ? (
            <button
              type="button"
              className="btn"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
            >
              {open ? "Collapse" : "Expand"}
            </button>
          ) : null}
          <button type="button" className="btn" onClick={onRegenerate} disabled={loading}>
            {isRegenerating ? "Regenerating..." : "Regenerate"}
          </button>
        </div>
      </div>

      {(!collapsible || open) && (
        <div className="mt-3">
          {status === "loading" ? (
            <div className="space-y-2">
              <div className="book-skeleton-line" style={{ width: "88%" }} />
              <div className="book-skeleton-line" style={{ width: "76%" }} />
              <div className="book-skeleton-line" style={{ width: "64%" }} />
            </div>
          ) : null}

          {status === "error" ? (
            <div className="rounded-md border border-red-400/50 bg-red-50 p-3">
              <p className="text-sm text-red-700">{error ?? "Could not load section."}</p>
              <button type="button" className="btn mt-2" onClick={onRetry}>
                Retry
              </button>
            </div>
          ) : null}

          {status === "success" ? children : null}
          {status === "idle" ? <p className="text-secondary">Not loaded yet.</p> : null}
        </div>
      )}
    </section>
  );
}
