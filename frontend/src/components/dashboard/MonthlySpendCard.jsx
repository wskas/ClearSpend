import { useState } from "react";
import { Copy, Check, ArrowUpRight, Plus, RefreshCcw } from "lucide-react";
import Card from "../shared/Card.jsx";
import CardHeader from "../shared/CardHeader.jsx";
import { fmtMoney, getBaseCurrency } from "../../utils/currency.js";

export default function MonthlySpendCard({ t, monthlyTotal, onAddSubscription }) {
  const [copied, setCopied] = useState(false);
  const baseCurrency = getBaseCurrency();

  return (
    <Card t={t}>
      <CardHeader t={t} label="Monthly Spend" tooltip="Normalized to USD across all active subscriptions" pill="Aug" />
      <div className="text-[30px] font-extrabold mt-1">{fmtMoney(monthlyTotal)}</div>
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => {
            navigator?.clipboard?.writeText?.(baseCurrency);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }}
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11.5px] font-medium"
          style={{ border: `1px solid ${t.border}`, color: t.textMuted }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />} {baseCurrency} base
        </button>
        <span className="flex items-center gap-1 rounded-md px-2 py-1 text-[11.5px] font-semibold" style={{ background: t.tealSoft, color: t.teal }}>
          <ArrowUpRight size={12} /> 4.2%
        </span>
      </div>
      <div className="flex gap-2 mt-4">
        <button onClick={onAddSubscription} className="flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2.5 text-[13px] font-semibold text-white" style={{ background: t.primary }}>
          <Plus size={14} /> Add subscription
        </button>
        <button className="flex items-center justify-center rounded-lg px-3" style={{ border: `1px solid ${t.border}` }}>
          <RefreshCcw size={14} style={{ color: t.textMuted }} />
        </button>
      </div>
    </Card>
  );
}
