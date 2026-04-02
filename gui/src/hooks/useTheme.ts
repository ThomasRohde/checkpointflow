import { useState, useEffect, useMemo } from "react";
import {
  webDarkTheme,
  webLightTheme,
  type Theme,
} from "@fluentui/react-components";

export type ThemeMode = "light" | "dark" | "system";

const THEME_KEY = "cpf_theme_mode";

function getSystemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveTheme(mode: ThemeMode): Theme {
  if (mode === "system") {
    return getSystemPrefersDark() ? webDarkTheme : webLightTheme;
  }
  return mode === "dark" ? webDarkTheme : webLightTheme;
}

function resolveDockviewClass(mode: ThemeMode): string {
  if (mode === "system") {
    return getSystemPrefersDark()
      ? "dockview-theme-abyss"
      : "dockview-theme-light";
  }
  return mode === "dark" ? "dockview-theme-abyss" : "dockview-theme-light";
}

export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
    return "dark";
  });

  // Track system preference changes when mode is "system"
  const [systemDark, setSystemDark] = useState(getSystemPrefersDark);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const setMode = (newMode: ThemeMode) => {
    setModeState(newMode);
    localStorage.setItem(THEME_KEY, newMode);
  };

  const fluentTheme = useMemo(() => {
    if (mode === "system") {
      return systemDark ? webDarkTheme : webLightTheme;
    }
    return resolveTheme(mode);
  }, [mode, systemDark]);

  const dockviewClass = useMemo(() => {
    if (mode === "system") {
      return systemDark ? "dockview-theme-abyss" : "dockview-theme-light";
    }
    return resolveDockviewClass(mode);
  }, [mode, systemDark]);

  const isDark = useMemo(() => {
    if (mode === "system") return systemDark;
    return mode === "dark";
  }, [mode, systemDark]);

  return { mode, setMode, fluentTheme, dockviewClass, isDark };
}
