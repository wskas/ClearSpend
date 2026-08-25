import { Pencil, Trash2 } from "lucide-react";
import Card from "../shared/Card.jsx";
import { CATEGORY_META } from "../../constants/categories.js";
import { fmtMoney } from "../../utils/currency.js";

export default function CategoryCard({ t, category, count, value, pct, onEdit, onDelete }) {
  const { name } = category;
  const color = category.hex_color_code || CATEGORY_META[name]?.color;
  return (
    <Card t={t}>
      <div className="flex items-center justify-between">
        <span className="rounded-full" style={{ width: 12, height: 12, background: color }} />
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold" style={{ color: t.textMuted }}>{count} sub{count !== 1 ? "s" : ""}</span>
          <button onClick={onEdit} title="Edit" className="flex items-center justify-center rounded-md" style={{ width: 26, height: 26, border: `1px solid ${t.border}`, color: t.textMuted }}>
            <Pencil size={12} />
          </button>
          <button onClick={onDelete} title="Delete" className="flex items-center justify-center rounded-md" style={{ width: 26, height: 26, border: `1px solid ${t.border}`, color: t.red }}>
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <div className="text-[15px] font-bold mt-3">{name}</div>
      <div className="text-[22px] font-extrabold mt-1">
        {fmtMoney(value)}<span className="text-[12px] font-medium" style={{ color: t.textMuted }}>/mo</span>
      </div>
      <div className="rounded-full overflow-hidden mt-3" style={{ height: 6, background: t.cardAlt }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 999 }} />
      </div>
      <div className="text-[11.5px] mt-1.5" style={{ color: t.textMuted }}>{pct.toFixed(1)}% of total spend</div>
    </Card>
  );
}
