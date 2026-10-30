import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no CSS.escape, which user-event needs to walk a radio group with the arrow keys.
if (!window.CSS) Object.defineProperty(window, "CSS", { value: {}, configurable: true });
if (!window.CSS.escape) window.CSS.escape = (value: string) => value.replace(/["\\]/g, "\\$&");

// jsdom has no modal <dialog>. The real focus and Escape behavior is covered by the browser tests.
if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
