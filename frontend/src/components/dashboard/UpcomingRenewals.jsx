import { fmtMoney, monthlyNormalized } from "../../utils/currency.js";
import { daysUntil, initials } from "../../utils/dates.js";

export default function UpcomingRenewals({ t, upcomingSorted, selectedRenewal, setSelectedRenewal }) {
  return (
    <>
      <div className="flex items-center justify-between">
        <div className="text-[14px] font-bold">Upcoming Renewals</div>
      </div>
      <div className="flex items-center gap-2.5 mt-4 overflow-x-auto p-1">
        {upcomingSorted.map((s) => {
          const color = s.color;
          return (
          <button
            key={s.id}
            onClick={() => setSelectedRenewal(s)}
            className="rounded-full flex items-center justify-center font-bold text-[11px] flex-shrink-0"
            title={`${s.name} · ${daysUntil(s.renews)}d`}
            style={{
              width: 38,
              height: 38,
              background: color + "22",
              color,
              outline: selectedRenewal?.id === s.id ? `2px solid ${color}` : "none",
              outlineOffset: 2,
            }}
          >
            {initials(s.name)}
          </button>
          );
        })}
      </div>
      {selectedRenewal ? (
        <div className="mt-4 rounded-lg p-3" style={{ background: t.cardAlt }}>
          <div className="text-[13px] font-semibold">{selectedRenewal.name}</div>
          <div className="text-[11.5px] mt-0.5" style={{ color: t.textMuted }}>{selectedRenewal.category} · {selectedRenewal.cycle}</div>
          <div className="flex items-center justify-between mt-2">
            <span className="text-[12px]" style={{ color: t.textMuted }}>Renews {selectedRenewal.renews}</span>
            <span className="text-[13px] font-bold">{fmtMoney(monthlyNormalized(selectedRenewal))}</span>
          </div>
        </div>
      ) : (
        <p className="text-[11.5px] mt-4" style={{ color: t.textFaint }}>Tap a subscription to see its renewal details.</p>
      )}
    </>
  );
}
