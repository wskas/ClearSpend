import { LayoutGrid } from "lucide-react";
import Card from "./Card.jsx";

export default function EmptyState({ t, tab, onBack }) {
  return (
    <Card t={t} className="flex flex-col items-center justify-center text-center py-16">
      <div
        className="rounded-full flex items-center justify-center mb-4"
        style={{ width: 48, height: 48, background: t.primarySoft }}
      >
        <LayoutGrid size={20} style={{ color: t.primary }} />
      </div>
      <div className="text-[15px] font-bold capitalize">{tab} isn't wired up in this prototype</div>
      <p className="text-[12.5px] mt-1 max-w-sm" style={{ color: t.textMuted }}>
        The shell and navigation are ready — this is where{" "}
        {tab === "analytics"
          ? "deeper reporting on FX trends and renewal forecasts"
          : "profile, base currency, and notification preferences"}{" "}
        would live.
      </p>
      <button
        onClick={onBack}
        className="cs-tap mt-4 rounded-lg px-4 py-2 text-[13px] font-semibold text-white"
        style={{ background: t.primary }}
      >
        Back to dashboard
      </button>
    </Card>
  );
}
