import { contactHref } from "./canvas/templates/content";

/**
 * Turn what a person typed into an address that is safe to link to, or null. It accepts a full web
 * address, a mail address, a phone number or a bare site such as github.com/asha, and writes the
 * scheme for them. The server checks again: only https, http, mailto and tel are kept.
 */
export function toHref(input: string): string | null {
  const value = input.trim();
  if (!value || value.length > 2048 || /[\s<>"`]/.test(value)) return null;
  if (/^https?:\/\/[^/?#]+/i.test(value)) {
    try {
      return new URL(value).hostname ? value : null;
    } catch {
      return null;
    }
  }
  if (/^mailto:[^\s@]+@[^\s@]+\.[^\s@]+$/i.test(value)) return value;
  if (/^tel:\+?[\d().-]{6,}$/i.test(value)) return value;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value) && !/^[^\s@]+@/.test(value)) return null;
  return contactHref(value) ?? null;
}
