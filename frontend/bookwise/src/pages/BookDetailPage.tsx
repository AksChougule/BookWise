import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import type { GenerationSection } from "../api/books";
import { BookHeader } from "../components/BookHeader";
import { ErrorState } from "../components/ErrorState";
import { JsonPretty } from "../components/JsonPretty";
import { SectionCard } from "../components/SectionCard";
import { SkeletonBookHeader } from "../components/SkeletonBookHeader";
import { useBook } from "../hooks/useBook";
import { useGenerationSection } from "../hooks/useGenerationSection";

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function renderOverview(content: Record<string, unknown>) {
  const overview = typeof content.overview === "string" ? content.overview : null;
  const readingTime =
    typeof content.reading_time_minutes === "number" ? content.reading_time_minutes : null;

  return (
    <div className="space-y-2">
      {overview ? <p style={{ whiteSpace: "pre-wrap" }}>{overview}</p> : <JsonPretty value={content} />}
      {readingTime ? (
        <p className="text-sm text-secondary">Estimated reading time: {readingTime} min</p>
      ) : null}
    </div>
  );
}

function renderKeyIdeas(content: Record<string, unknown>) {
  const ideas = Array.isArray(content.key_ideas) ? content.key_ideas : null;
  if (!ideas) {
    return <JsonPretty value={content} />;
  }

  return (
    <ol className="space-y-2" style={{ paddingLeft: "1.2rem" }}>
      {ideas.map((item, index) => {
        if (typeof item === "string") {
          return <li key={index}>{item}</li>;
        }
        if (item && typeof item === "object") {
          const record = item as Record<string, unknown>;
          const title = typeof record.title === "string" ? record.title : `Idea ${index + 1}`;
          const explanation =
            typeof record.explanation === "string"
              ? record.explanation
              : typeof record.summary === "string"
                ? record.summary
                : null;
          return (
            <li key={index}>
              <p className="font-medium">{title}</p>
              {explanation ? <p className="text-secondary">{explanation}</p> : null}
            </li>
          );
        }
        return <li key={index}>{String(item)}</li>;
      })}
    </ol>
  );
}

function renderChapters(content: Record<string, unknown>) {
  const chapters = Array.isArray(content.chapters) ? content.chapters : null;
  if (!chapters) {
    return <JsonPretty value={content} />;
  }

  return (
    <div className="space-y-2">
      {chapters.map((chapter, index) => {
        const record = asObject(chapter);
        const title =
          typeof record.title === "string" && record.title.trim().length > 0
            ? record.title
            : `Chapter ${index + 1}`;
        const summary =
          typeof record.summary === "string"
            ? record.summary
            : typeof record.content === "string"
              ? record.content
              : "No summary available.";

        return (
          <details key={`${title}-${index}`} className="rounded-md border border-app bg-muted p-2" open={index === 0}>
            <summary className="cursor-pointer font-medium">{title}</summary>
            <p className="mt-2 text-sm text-secondary" style={{ whiteSpace: "pre-wrap" }}>
              {summary}
            </p>
          </details>
        );
      })}
    </div>
  );
}

function renderCritique(content: Record<string, unknown>) {
  const strengths = Array.isArray(content.strengths) ? content.strengths : null;
  const weaknesses = Array.isArray(content.weaknesses) ? content.weaknesses : null;
  const who = Array.isArray(content.who_should_read) ? content.who_should_read : null;

  if (!strengths && !weaknesses && !who) {
    return <JsonPretty value={content} />;
  }

  const renderList = (title: string, items: unknown[] | null) => (
    <div>
      <h3 className="text-sm font-semibold text-secondary">{title}</h3>
      {items && items.length > 0 ? (
        <ul className="mt-1 space-y-1" style={{ paddingLeft: "1rem" }}>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{String(item)}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-secondary">Not provided.</p>
      )}
    </div>
  );

  return (
    <div className="space-y-3">
      {renderList("Strengths", strengths)}
      {renderList("Weaknesses", weaknesses)}
      {renderList("Who it\'s for", who)}
    </div>
  );
}

function sectionTitle(section: GenerationSection): string {
  switch (section) {
    case "overview":
      return "Overview";
    case "key_ideas":
      return "Key ideas";
    case "chapters":
      return "Chapter-wise summary";
    case "critique":
      return "Critique";
  }
}

function renderSection(section: GenerationSection, content: Record<string, unknown>) {
  switch (section) {
    case "overview":
      return renderOverview(content);
    case "key_ideas":
      return renderKeyIdeas(content);
    case "chapters":
      return renderChapters(content);
    case "critique":
      return renderCritique(content);
  }
}

export default function BookDetailPage() {
  const { workId } = useParams();
  const { data, isLoading, error, refetch } = useBook(workId);

  const overview = useGenerationSection(workId ?? "", "overview", { auto: Boolean(workId) });
  const keyIdeas = useGenerationSection(workId ?? "", "key_ideas", { auto: Boolean(workId) });
  const chapters = useGenerationSection(workId ?? "", "chapters", { auto: Boolean(workId) });
  const critique = useGenerationSection(workId ?? "", "critique", { auto: Boolean(workId) });

  useEffect(() => {
    if (data?.title) {
      document.title = `${data.title} – BookWise`;
      return;
    }
    document.title = "BookWise";
  }, [data]);

  const sections: Array<{
    key: GenerationSection;
    state: ReturnType<typeof useGenerationSection>;
    collapsible: boolean;
    defaultOpen: boolean;
  }> = [
    { key: "overview", state: overview, collapsible: false, defaultOpen: true },
    { key: "key_ideas", state: keyIdeas, collapsible: true, defaultOpen: true },
    { key: "chapters", state: chapters, collapsible: true, defaultOpen: false },
    { key: "critique", state: critique, collapsible: true, defaultOpen: false },
  ];

  return (
    <section className="space-y-4">
      <p>
        <Link to="/" className="book-link text-sm">
          ← Back to search
        </Link>
      </p>

      {isLoading ? <SkeletonBookHeader /> : null}
      {!isLoading && error ? (
        <ErrorState title="Could not load this book" message={error} onRetry={() => void refetch()} />
      ) : null}
      {!isLoading && !error && data ? <BookHeader book={data} /> : null}

      {!isLoading && !error && data ? (
        <section className="space-y-3">
          <h2 className="text-2xl font-semibold">Generated insights</h2>
          {sections.map(({ key, state, collapsible, defaultOpen }) => (
            <SectionCard
              key={key}
              title={sectionTitle(key)}
              status={state.status}
              stored={state.stored}
              error={state.error}
              hasContent={state.data !== null}
              onRetry={() => void state.refresh(false)}
              onRegenerate={() => void state.refresh(true)}
              collapsible={collapsible}
              defaultOpen={defaultOpen}
            >
              {state.data ? renderSection(key, state.data) : <p className="text-secondary">No content yet.</p>}
            </SectionCard>
          ))}
        </section>
      ) : null}
    </section>
  );
}
