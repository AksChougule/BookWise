export function SkeletonBookHeader() {
  return (
    <section className="rounded-xl border border-app bg-surface p-6">
      <div className="book-header-layout">
        <div className="book-cover-skeleton" />
        <div className="space-y-3">
          <div className="book-skeleton-line" style={{ width: "70%" }} />
          <div className="book-skeleton-line" style={{ width: "50%" }} />
          <div className="book-skeleton-line" style={{ width: "90%" }} />
          <div className="book-skeleton-line" style={{ width: "85%" }} />
          <div className="book-skeleton-line" style={{ width: "65%" }} />
        </div>
      </div>
    </section>
  );
}
