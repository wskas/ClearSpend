import { useEffect } from "react";

// Pushes the active theme's background onto the document itself.
//
// AppShell/AuthShell paint their background on a div inside #root, which
// leaves <html> at the browser default — visible on mobile wherever the page
// is painted outside #root: the overscroll bounce at the top and bottom, and
// the strip behind the collapsing browser chrome. `--app-bg` is consumed by
// html/body in index.css, `color-scheme` themes native UI (scrollbars, form
// controls, the overscroll gutter), and `theme-color` tints the browser's own
// chrome on mobile so it doesn't sit as a white bar above a dark page.
export function useDocumentTheme(bg, dark) {
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--app-bg", bg);
    root.style.colorScheme = dark ? "dark" : "light";

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = bg;
  }, [bg, dark]);
}
