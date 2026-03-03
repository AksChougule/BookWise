import React from "react";

type JsonPrettyProps = {
  value: unknown;
};

function renderPrimitive(value: unknown): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-secondary">—</span>;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

export function JsonPretty({ value }: JsonPrettyProps) {
  const primitive = renderPrimitive(value);
  if (primitive !== null) {
    return <p className="text-primary">{primitive}</p>;
  }

  if (Array.isArray(value)) {
    return (
      <ul className="space-y-2">
        {value.map((item, index) => (
          <li key={index} className="rounded-md border border-app bg-muted p-2">
            <JsonPretty value={item} />
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object" && value !== null) {
    return (
      <div className="space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key} className="rounded-md border border-app bg-muted p-2">
            <p className="text-xs font-semibold uppercase text-secondary">{key.replaceAll("_", " ")}</p>
            <div className="mt-1">
              <JsonPretty value={item} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return null;
}
