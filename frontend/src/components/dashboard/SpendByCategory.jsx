import { CATEGORY_META } from "../../constants/categories.js";

export default function SpendByCategory({ t, categoryTotals }) {
  return (
    <div className="mt-5 pt-4" style={{ borderTop: `1px solid ${t.border}` }}>
      <div className="text-[14px] font-bold mb-3">Spend by Category</div>
      <div className="flex flex-col gap-3">
        {categoryTotals.map((c) => (
          <div key={c.name}>
            <div className="flex justify-between text-[11.5px] mb-1">
              <span style={{ color: t.textMuted }}>{c.name}</span>
              <span className="font-semibold cs-num">{c.pct.toFixed(0)}%</span>
            </div>
            <div className="rounded-full overflow-hidden" style={{ height: 6, background: t.cardAlt }}>
              <div style={{ width: `${c.pct}%`, height: "100%", background: c.color || CATEGORY_META[c.name]?.color, borderRadius: 999 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
