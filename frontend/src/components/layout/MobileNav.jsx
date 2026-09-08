import { useEffect, useState } from "react";
import { X } from "lucide-react";
import SidebarContent from "./SidebarContent.jsx";

// Kept in sync with the `transition` durations below -- the exit timer decides
// when the drawer actually leaves the DOM, so it must not fire before the
// slide-out has finished painting.
const ENTER_MS = 280;
const EXIT_MS = 200;

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia(REDUCED_MOTION_QUERY).matches);

  useEffect(() => {
    const mq = window.matchMedia(REDUCED_MOTION_QUERY);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

// Slide-in drawer that carries the sidebar below the `md` breakpoint, where
// Sidebar.jsx is hidden. It renders the same SidebarContent, so tab switching,
// logout and the theme toggle are all reachable on a phone.
export default function MobileNav({ t, dark, setDark, tab, setTab, open, onClose }) {
  const reducedMotion = usePrefersReducedMotion();
  const exitMs = reducedMotion ? 0 : EXIT_MS;

  // Three pieces of state, deliberately. `closing` keeps the drawer in the DOM
  // through its exit animation and `shown` drives the transform/opacity; a
  // single `open` flag would unmount the node before it had anything to
  // animate to, which is exactly the instant-disappear this replaces.
  // `prevOpen` is the render-phase "adjust state when a prop changes" pattern
  // -- doing this in an effect costs an extra paint, and the closed drawer
  // would flash on screen for that frame.
  const [prevOpen, setPrevOpen] = useState(open);
  const [closing, setClosing] = useState(false);
  const [shown, setShown] = useState(false);
  const mounted = open || closing;

  if (prevOpen !== open) {
    setPrevOpen(open);
    if (open) {
      setClosing(false);
    } else {
      setClosing(true);
      setShown(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    // Two frames between mount and `shown` so the browser paints the closed
    // state first. Flipping both in one paint means no transition at all.
    let inner;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => setShown(true));
    });
    return () => {
      cancelAnimationFrame(outer);
      if (inner) cancelAnimationFrame(inner);
    };
  }, [open]);

  useEffect(() => {
    if (!closing) return;
    const id = setTimeout(() => setClosing(false), exitMs);
    return () => clearTimeout(id);
  }, [closing, exitMs]);

  // Close on Escape and freeze the page behind the drawer. Keyed on `mounted`,
  // not `open`, so the scrollbar doesn't pop back mid slide-out.
  useEffect(() => {
    if (!mounted) return;

    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [mounted, onClose]);

  if (!mounted) return null;

  const ease = shown ? "cubic-bezier(0.32, 0.72, 0, 1)" : "cubic-bezier(0.4, 0, 1, 1)";
  const duration = shown ? ENTER_MS : EXIT_MS;
  const transition = reducedMotion ? "none" : `transform ${duration}ms ${ease}, opacity ${duration}ms ease`;

  return (
    <div className="md:hidden fixed inset-0 z-50 flex">
      <div
        onClick={onClose}
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background: "rgba(10,12,22,0.55)",
          opacity: shown ? 1 : 0,
          transition: reducedMotion ? "none" : `opacity ${duration}ms ease`,
        }}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Main menu"
        className="relative flex flex-col justify-between h-full overflow-y-auto"
        style={{
          width: 260,
          maxWidth: "82vw",
          background: t.sidebar,
          borderRight: `1px solid ${t.border}`,
          transform: shown ? "translateX(0)" : "translateX(-100%)",
          willChange: "transform",
          transition,
        }}
      >
        <button
          onClick={onClose}
          aria-label="Close menu"
          className="absolute flex items-center justify-center rounded-lg"
          style={{
            top: 14,
            right: 12,
            width: 32,
            height: 32,
            color: t.textMuted,
            opacity: shown ? 1 : 0,
            transition: reducedMotion ? "none" : `opacity ${duration}ms ease ${shown ? "120ms" : "0ms"}`,
          }}
        >
          <X size={17} />
        </button>

        <SidebarContent t={t} dark={dark} setDark={setDark} tab={tab} setTab={setTab} onNavigate={onClose} />
      </aside>
    </div>
  );
}
