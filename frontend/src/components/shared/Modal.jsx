import { X } from "lucide-react";

// Simple centered modal. Click the backdrop or the X to close; clicks inside
// the card don't propagate to the backdrop.
export default function Modal({ t, title, onClose, children }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(10,12,20,0.45)" }}
      onClick={onClose}
    >
      <div
        className="w-full rounded-2xl p-6"
        style={{ maxWidth: 440, background: t.card, border: `1px solid ${t.border}`, boxShadow: t.shadow }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="text-[16px] font-bold">{title}</div>
          <button onClick={onClose} className="cs-tap">
            <X size={16} style={{ color: t.textMuted }} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
