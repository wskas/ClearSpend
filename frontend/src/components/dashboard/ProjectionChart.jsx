import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import Card from "../shared/Card.jsx";
import ProjectionTooltip from "./ProjectionTooltip.jsx";
import { getBaseCurrency } from "../../utils/currency.js";

const HORIZONS = [3, 6, 12];
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// The backend projects a flat monthly spend (no future changes are modeled),
// so we repeat the current per-category breakdown across the horizon, labeled
// with the upcoming calendar months.
function buildSeries(categoryTotals, horizon) {
  const perCategory = {};
  categoryTotals.forEach((c) => {
    perCategory[c.name] = Number(c.value.toFixed(2));
  });

  const now = new Date();
  return Array.from({ length: horizon }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    return { month: MONTH_LABELS[d.getMonth()], ...perCategory };
  });
}

export default function ProjectionChart({ t, horizon, setHorizon, categoryTotals = [] }) {
  const chartData = buildSeries(categoryTotals, horizon);
  const colorByName = Object.fromEntries(categoryTotals.map((c) => [c.name, c.color]));
  const categories = categoryTotals.map((c) => c.name);

  return (
    <Card t={t} className="lg:col-span-2">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[14px] font-bold">Cost Projection</div>
          <div className="text-[11.5px]" style={{ color: t.textMuted }}>Stacked by category, normalized to {getBaseCurrency()}</div>
        </div>
        <div className="flex rounded-lg p-0.5" style={{ background: t.cardAlt, border: `1px solid ${t.border}` }}>
          {HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className="rounded-md px-3 py-1.5 text-[12px] font-semibold"
              style={{ background: horizon === h ? t.primary : "transparent", color: horizon === h ? "#fff" : t.textMuted }}
            >
              {h}mo
            </button>
          ))}
        </div>
      </div>
      <div style={{ height: 260 }} className="mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} barGap={4} barCategoryGap={horizon > 6 ? "18%" : "30%"}>
            <CartesianGrid vertical={false} stroke={t.border} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: t.textMuted }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: t.textMuted }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} width={44} />
            <Tooltip content={<ProjectionTooltip t={t} />} cursor={{ fill: t.cardAlt }} />
            {categories.map((cat, i, arr) => (
              <Bar
                key={cat}
                dataKey={cat}
                stackId="cost"
                fill={colorByName[cat]}
                radius={i === arr.length - 1 ? [5, 5, 0, 0] : [0, 0, 0, 0]}
                maxBarSize={40}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap gap-4 mt-3">
        {categories.map((name) => (
          <span key={name} className="flex items-center gap-1.5 text-[11.5px]" style={{ color: t.textMuted }}>
            <span className="rounded-full" style={{ width: 8, height: 8, background: colorByName[name] }} /> {name}
          </span>
        ))}
      </div>
    </Card>
  );
}
