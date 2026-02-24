import { useMemo } from "react";

type JsonViewerProps = {
  data: unknown;
  title?: string;
  defaultCollapsed?: boolean;
};

export function JsonViewer({ data, title = "JSON", defaultCollapsed = false }: JsonViewerProps) {
  const content = useMemo(() => JSON.stringify(data, null, 2), [data]);

  return (
    <details className="rounded-md border border-app bg-muted" open={!defaultCollapsed}>
      <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-primary">
        {title}
      </summary>
      <pre className="max-h-80 overflow-auto border-t border-app p-3 text-xs text-primary">{content}</pre>
    </details>
  );
}
