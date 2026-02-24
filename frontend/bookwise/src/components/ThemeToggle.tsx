import { useTheme, type ThemeSetting } from "../hooks/useTheme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <label className="inline-flex items-center gap-2 text-sm text-secondary">
      <span>Theme</span>
      <select
        className="rounded-md border border-app bg-surface px-2 py-1 text-primary focus-visible:ring"
        value={theme}
        onChange={(event) => setTheme(event.target.value as ThemeSetting)}
        aria-label="Theme"
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
    </label>
  );
}
