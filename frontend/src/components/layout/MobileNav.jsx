import { useEffect } from "react";
import { X } from "lucide-react";
import SidebarContent from "./SidebarContent.jsx";

// Slide-in drawer that carries the sidebar below the `md` breakpoint, where
// Sidebar.jsx is hidden. It renders the same SidebarContent, so tab switching,
// logout and the theme toggle are all reachable on a phone.
export default function MobileNav({ t, dark, setDark, tab, setTab, open, onClose }) {
  // Close on Escape and freeze the page behind the drawer while it is open.
  useEffect(() => {
    if (!open) return;

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
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="md:hidden fixed inset-0 z-50 flex">
      <div
        onClick={onClose}
        aria-hidden="true"
        className="absolute inset-0"
        style={{ background: "rgba(10,12,22,0.55)" }}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Main menu"
        className="relative flex flex-col justify-between h-full overflow-y-auto"
        style={{ width: 260, maxWidth: "82vw", background: t.sidebar, borderRight: `1px solid ${t.border}` }}
      >
        <button
          onClick={onClose}
          aria-label="Close menu"
          className="absolute flex items-center justify-center rounded-lg"
          style={{ top: 14, right: 12, width: 32, height: 32, color: t.textMuted }}
        >
          <X size={17} />
        </button>

        <SidebarContent t={t} dark={dark} setDark={setDark} tab={tab} setTab={setTab} onNavigate={onClose} />
      </aside>
    </div>
  );
}
