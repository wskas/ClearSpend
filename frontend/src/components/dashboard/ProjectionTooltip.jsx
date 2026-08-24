import { fmtMoney } from "../../utils/currency.js";

export default function ProjectionTooltip({ active, payload, label, t }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + p.value, 0);
  return (
    <div className="rounded-lg p-3" style={{ background: t.card, border: `1px solid ${t.border}`, boxShadow: t.shadow }}>
      <div className="text-[12px] font-bold mb-1.5">{label} · {fmtMoney(total)}</div>
      {payload.slice().reverse().map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 text-[11.5px]">
          <span className="flex items-center gap-1.5" style={{ color: t.textMuted }}>
            <span className="rounded-full" style={{ width: 7, height: 7, background: p.fill }} /> {p.dataKey}
          </span>
          <span className="font-semibold cs-num">{fmtMoney(p.value)}</span>
        </div>
      ))}
    </div>
  );
}
