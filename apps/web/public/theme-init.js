// Runs before first paint (loaded synchronously from <head>) so the stored theme is applied
// before any content is drawn and the page never flashes the wrong theme.
// Kept in a same-origin file, not inline, so a strict Content-Security-Policy can allow it.
// Keep the storage key and the values in sync with src/lib/theme.ts.
(function () {
  try {
    var stored = window.localStorage.getItem("pv-theme");
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (error) {
    // Storage can be blocked. The operating system preference then applies.
  }
})();
