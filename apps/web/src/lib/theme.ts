// Theme preference: "system" follows the operating system, "light" and "dark" override it.
// The choice lives in localStorage so it survives reloads. public/theme-init.js applies it before
// first paint and must use the same key and values.
import { useCallback, useSyncExternalStore } from "react";

export type ThemeChoice = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "pv-theme";
export const THEME_CHOICES: readonly ThemeChoice[] = ["system", "light", "dark"];

export function parseTheme(value: string | null | undefined): ThemeChoice {
  return value === "light" || value === "dark" ? value : "system";
}

export function readStoredTheme(): ThemeChoice {
  try {
    return parseTheme(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return "system";
  }
}

/** What is applied right now. The attribute on <html> is the source of truth, even if storage is blocked. */
export function currentTheme(): ThemeChoice {
  return parseTheme(document.documentElement.getAttribute("data-theme"));
}

/** Sets or clears data-theme on <html>. "system" removes it so the operating system decides. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

export function saveTheme(choice: ThemeChoice): void {
  applyTheme(choice);
  try {
    if (choice === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Storage can be blocked (private windows, site data off). The choice still applies for this visit.
  }
  listeners.forEach((listener) => listener());
}

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** The current choice and a setter. Re-renders every user of the hook when the choice changes. */
export function useTheme(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const choice = useSyncExternalStore(subscribe, currentTheme, () => "system" as ThemeChoice);
  const setChoice = useCallback((next: ThemeChoice) => saveTheme(next), []);
  return [choice, setChoice];
}
