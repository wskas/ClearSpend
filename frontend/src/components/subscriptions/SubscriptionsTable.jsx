import { Pencil, Trash2 } from "lucide-react";
import { fmtMoney, monthlyNormalized } from "../../utils/currency.js";
import { initials } from "../../utils/dates.js";

export default function SubscriptionsTable({ t, subs, compact, onEdit, onDelete }) {
  const showActions = !compact && onEdit && onDelete;
  const colCount = 5 + (compact ? 0 : 1) + (showActions ? 1 : 0);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr style={{ borderBottom: `1px solid ${t.border}` }}>
            <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pr-3" style={{ color: t.textFaint }}>Name</th>
            <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pr-3" style={{ color: t.textFaint }}>Category</th>
            <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pr-3" style={{ color: t.textFaint }}>Cycle</th>
            <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pr-3" style={{ color: t.textFaint }}>Renews</th>
            {!compact && <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pr-3" style={{ color: t.textFaint }}>Status</th>}
            <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 text-right" style={{ color: t.textFaint }}>Monthly</th>
            {showActions && <th className="text-[11px] font-semibold uppercase tracking-wide pb-2 pl-3 text-right" style={{ color: t.textFaint }}>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {subs.length === 0 && (
            <tr><td colSpan={colCount} className="py-6 text-center text-[12.5px]" style={{ color: t.textFaint }}>No subscriptions match this filter.</td></tr>
          )}
          {subs.map((s) => {
            const color = s.color;
            return (
            <tr key={s.id} style={{ borderBottom: `1px solid ${t.border}` }}>
              <td className="py-2.5 pr-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className="rounded-lg flex items-center justify-center font-bold text-[10.5px] flex-shrink-0"
                    style={{ width: 30, height: 30, background: color + "22", color }}
                  >
                    {initials(s.name)}
                  </div>
                  <span className="text-[13px] font-medium">{s.name}</span>
                </div>
              </td>
              <td className="py-2.5 pr-3">
                <span
                  className="text-[11.5px] font-medium rounded-full px-2 py-0.5"
                  style={{ background: color + "1A", color }}
                >
                  {s.category}
                </span>
              </td>
              <td className="py-2.5 pr-3 text-[12.5px]" style={{ color: t.textMuted }}>{s.cycle}</td>
              <td className="py-2.5 pr-3 text-[12.5px]" style={{ color: t.textMuted }}>{s.renews}</td>
              {!compact && (
                <td className="py-2.5 pr-3">
                  <span
                    className="text-[11.5px] font-medium rounded-full px-2 py-0.5"
                    style={{ background: s.active ? "#12B3A01A" : "#8A8FA61A", color: s.active ? "#12B3A0" : "#8A8FA6" }}
                  >
                    {s.active ? "Active" : "Inactive"}
                  </span>
                </td>
              )}
              <td className="py-2.5 text-right text-[13px] font-semibold" style={{ color: t.red }}>
                −{fmtMoney(monthlyNormalized(s))}
              </td>
              {showActions && (
                <td className="py-2.5 pl-3">
                  <div className="flex items-center justify-end gap-1.5">
                    <button
                      onClick={() => onEdit(s)}
                      title="Edit"
                      className="flex items-center justify-center rounded-md"
                      style={{ width: 28, height: 28, border: `1px solid ${t.border}`, color: t.textMuted }}
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => onDelete(s)}
                      title="Delete"
                      className="flex items-center justify-center rounded-md"
                      style={{ width: 28, height: 28, border: `1px solid ${t.border}`, color: t.red }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </td>
              )}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
