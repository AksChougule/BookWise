type ErrorStateProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
};

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <section className="rounded-xl border border-app bg-surface p-6">
      <h2 className="text-lg font-semibold text-primary">{title}</h2>
      <p className="mt-2 text-sm text-secondary">{message}</p>
      {onRetry ? (
        <div className="mt-2">
          <button type="button" className="btn" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}
    </section>
  );
}
