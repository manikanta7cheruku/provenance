import { request } from "./api";

/** A saved look: a font pair and four colors. No words and no pictures. */
export interface StudioTheme {
  id: string;
  name: string;
  font_pair: string;
  accent: string;
  ink: string;
  muted: string;
  tint: string;
  updated_at: string;
}

export interface StudioThemes {
  themes: StudioTheme[];
  count: number;
  max_themes: number;
}

export type ThemeBody = Omit<StudioTheme, "id" | "updated_at">;

const BASE = "/api/v1/studio/themes";

export function fetchThemes(signal?: AbortSignal): Promise<StudioThemes> {
  return request<StudioThemes>("GET", BASE, { signal });
}

export function createTheme(body: ThemeBody): Promise<StudioTheme> {
  return request<StudioTheme>("POST", BASE, { body });
}

export function replaceTheme(id: string, body: ThemeBody): Promise<StudioTheme> {
  return request<StudioTheme>("PUT", `${BASE}/${encodeURIComponent(id)}`, { body });
}

export function deleteTheme(id: string): Promise<void> {
  return request<void>("DELETE", `${BASE}/${encodeURIComponent(id)}`);
}

/** The look of a resume, in the shape a theme is saved in. */
export function lookOf(style: { font_pair: string; accent: string; ink: string; muted: string; tint: string }): Omit<ThemeBody, "name"> {
  return { font_pair: style.font_pair, accent: style.accent, ink: style.ink, muted: style.muted, tint: style.tint };
}

/** Whether a resume currently has exactly this look. */
export function sameLook(
  style: { font_pair: string; accent: string; ink: string; muted: string; tint: string },
  theme: Omit<ThemeBody, "name">,
): boolean {
  return (
    style.font_pair === theme.font_pair &&
    style.accent === theme.accent &&
    style.ink === theme.ink &&
    style.muted === theme.muted &&
    style.tint === theme.tint
  );
}
