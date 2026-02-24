import { useEffect, useMemo, useState } from "react";

export type ThemeSetting = "light" | "dark" | "system";

const STORAGE_KEY = "theme";

function readStoredTheme(): ThemeSetting {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }
  return "system";
}

function detectSystemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyThemeClass(theme: ThemeSetting): void {
  const isDark = theme === "dark" || (theme === "system" && detectSystemDark());
  document.documentElement.classList.toggle("dark", isDark);
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeSetting>(() => readStoredTheme());

  useEffect(() => {
    applyThemeClass(theme);
    localStorage.setItem(STORAGE_KEY, theme);

    if (theme !== "system") {
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => applyThemeClass("system");
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [theme]);

  const resolvedTheme = useMemo(() => {
    if (theme === "system") {
      return detectSystemDark() ? "dark" : "light";
    }
    return theme;
  }, [theme]);

  const setTheme = (value: ThemeSetting) => setThemeState(value);

  return { theme, resolvedTheme, setTheme };
}
