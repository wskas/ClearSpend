import Card from "../shared/Card.jsx";
import CardHeader from "../shared/CardHeader.jsx";
import { fmtMoney } from "../../utils/currency.js";
import { CATEGORY_META } from "../../constants/categories.js";

export default function AvgCostCard({ t, monthlyTotal, subsCount, categoryTotals }) {
  return (
    <Card t={t}>
      <CardHeader t={t} label="Avg. Cost / Subscription" tooltip="Monthly total divided by active subscriptions" pill="Aug" />
      <div className="cs-num text-[30px] font-extrabold mt-1">{fmtMoney(monthlyTotal / (subsCount || 1))}</div>
      <div className="flex items-center gap-1.5 mt-2 text-[11.5px] font-semibold" style={{ color: t.red }}>
        {/* <ArrowDownRight size={12} /> Down 2.1% vs last month */}
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {categoryTotals.slice(0, 3).map((c) => (
          <div key={c.name} className="flex items-center justify-between text-[12px]">
            <span className="flex items-center gap-2" style={{ color: t.textMuted }}>
              <span className="rounded-full" style={{ width: 7, height: 7, background: c.color || CATEGORY_META[c.name]?.color }} />
              {c.name}
            </span>
            <span className="font-semibold cs-num">{fmtMoney(c.value)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
