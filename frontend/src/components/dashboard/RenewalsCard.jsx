import Card from "../shared/Card.jsx";
import CardHeader from "../shared/CardHeader.jsx";
import { fmtMoney, monthlyNormalized } from "../../utils/currency.js";
import { daysUntil } from "../../utils/dates.js";

export default function RenewalsCard({ t, renewalsThisWeek, nextRenewal }) {
  const daysToNext = nextRenewal ? Math.max(0, daysUntil(nextRenewal.renews)) : 0;
  const ringDeg = Math.max(0, Math.min(360, (1 - daysToNext / 30) * 360));

  return (
    <Card t={t}>
      <CardHeader t={t} label="Renewals This Week" tooltip="Active subscriptions billing in the next 7 days" pill="7d" />
      <div className="cs-num text-[30px] font-extrabold mt-1">{renewalsThisWeek.length}</div>
      <div className="text-[12px] mt-1" style={{ color: t.textMuted }}>
        {renewalsThisWeek.length > 0 ? renewalsThisWeek.map((r) => r.name).join(", ") : "Nothing due in the next 7 days"}
      </div>
      <div className="flex items-center gap-3 mt-4">
        <div
          className="rounded-full flex items-center justify-center flex-shrink-0"
          style={{ width: 52, height: 52, background: `conic-gradient(${t.primary} ${ringDeg}deg, ${t.border} 0deg)` }}
        >
          <div className="rounded-full flex items-center justify-center cs-num font-bold text-[12px]" style={{ width: 40, height: 40, background: t.card }}>
            {nextRenewal ? daysToNext : "-"}d
          </div>
        </div>
        <div className="text-[12px]" style={{ color: t.textMuted }}>
          Next up: <span style={{ color: t.text, fontWeight: 600 }}>{nextRenewal?.name}</span>
          {nextRenewal && <> · {fmtMoney(monthlyNormalized(nextRenewal))}</>}
        </div>
      </div>
    </Card>
  );
}
