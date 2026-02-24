import type { KeyboardEvent } from "react";

type SearchBoxProps = {
  value: string;
  onChange: (next: string) => void;
  onSubmit?: () => void;
};

export function SearchBox({ value, onChange, onSubmit }: SearchBoxProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      onSubmit?.();
    }
  };

  return (
    <div className="rounded-xl border border-app bg-surface p-4">
      <label htmlFor="search-input" className="mb-2 block text-sm font-medium text-primary">
        Search books
      </label>
      <div className="flex items-center gap-2">
        <input
          id="search-input"
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search for an English book..."
          className="w-full rounded-md border border-app bg-surface px-3 py-2 text-primary focus-visible:ring"
        />
        <button
          type="button"
          className="btn"
          onClick={() => onChange("")}
          disabled={value.length === 0}
        >
          Clear
        </button>
      </div>
    </div>
  );
}
