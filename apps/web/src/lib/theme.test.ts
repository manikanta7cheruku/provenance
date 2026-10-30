import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { applyTheme, currentTheme, parseTheme, readStoredTheme, saveTheme, THEME_STORAGE_KEY, useTheme } from "./theme";

describe("parseTheme", () => {
  it("accepts light and dark and treats everything else as system", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("system")).toBe("system");
    expect(parseTheme("purple")).toBe("system");
    expect(parseTheme(null)).toBe("system");
    expect(parseTheme(undefined)).toBe("system");
  });
});

describe("applyTheme", () => {
  it("sets data-theme for an explicit choice and removes it for system", () => {
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    applyTheme("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});

describe("saveTheme", () => {
  it("stores an explicit choice and clears the key for system", () => {
    saveTheme("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readStoredTheme()).toBe("dark");
    saveTheme("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(readStoredTheme()).toBe("system");
  });

  it("still applies the choice when storage is blocked", () => {
    const blocked = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(() => saveTheme("dark")).not.toThrow();
    expect(currentTheme()).toBe("dark");
    blocked.mockRestore();
  });

  it("reads system when storage cannot be read", () => {
    const blocked = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(readStoredTheme()).toBe("system");
    blocked.mockRestore();
  });
});

describe("useTheme", () => {
  it("reports the applied theme and updates when it changes", () => {
    applyTheme("light");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
