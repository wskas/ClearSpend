import { AlertTriangle, X } from "lucide-react";

// Surfaces the `warnings` array from GET /api/analytics/projections/ (e.g.
// "Missing exchange rate for GBP"). Hidden when there's nothing to warn about.
export default function FxWarningBanner({ t, warnings = [], show, onDismiss }) {
  if (!show || warnings.length === 0) return null;
  return (
    <div className="flex items-start gap-3 rounded-xl px-4 py-3" style={{ background: t.amberSoft, border: `1px solid ${t.amber}55` }}>
      <AlertTriangle size={16} style={{ color: t.amber, marginTop: 2, flexShrink: 0 }} />
      <p className="text-[12.5px] flex-1" style={{ color: t.text }}>{warnings.join(" ")}</p>
      <button onClick={onDismiss} className="cs-tap">
        <X size={14} style={{ color: t.textMuted }} />
      </button>
    </div>
  );
}
