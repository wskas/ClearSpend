import { useState } from "react";
import Card from "../shared/Card.jsx";
import FxWarningBanner from "./FxWarningBanner.jsx";
import MonthlySpendCard from "./MonthlySpendCard.jsx";
import RenewalsCard from "./RenewalsCard.jsx";
import AvgCostCard from "./AvgCostCard.jsx";
import ProjectionChart from "./ProjectionChart.jsx";
import UpcomingRenewals from "./UpcomingRenewals.jsx";
import SpendByCategory from "./SpendByCategory.jsx";
import SubscriptionsTable from "../subscriptions/SubscriptionsTable.jsx";
import SubscriptionForm from "../subscriptions/SubscriptionForm.jsx";
import { useCategories } from "../../hooks/queries.js";
import { ChevronDown, Download } from "lucide-react";

export default function DashboardPage({
  t,
  firstName,
  monthlyTotal,
  categoryTotals,
  renewalsThisWeek,
  nextRenewal,
  upcomingSorted,
  selectedRenewal,
  setSelectedRenewal,
  horizon,
  setHorizon,
  showFxBanner,
  setShowFxBanner,
  warnings,
  filteredSubs,
  subsCount,
}) {
  const { data: categories = [] } = useCategories();
  const [adding, setAdding] = useState(false);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="cs-num text-[22px] font-bold">Welcome back{firstName ? `, ${firstName}` : ""} 👋</h2>
        <div className="flex items-center gap-2">
          <button className="cs-tap flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium" style={{ border: `1px solid ${t.border}`, color: t.textMuted }}>
            Aug 24, 2026 <ChevronDown size={14} />
          </button>
          <button className="cs-tap flex items-center gap-2 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white" style={{ background: t.primary }}>
            <Download size={14} /> Export
          </button>
        </div>
      </div>

      <FxWarningBanner t={t} warnings={warnings} show={showFxBanner} onDismiss={() => setShowFxBanner(false)} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <MonthlySpendCard t={t} monthlyTotal={monthlyTotal} onAddSubscription={() => setAdding(true)} />
        <RenewalsCard t={t} renewalsThisWeek={renewalsThisWeek} nextRenewal={nextRenewal} />
        <AvgCostCard t={t} monthlyTotal={monthlyTotal} subsCount={subsCount} categoryTotals={categoryTotals} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <ProjectionChart t={t} horizon={horizon} setHorizon={setHorizon} categoryTotals={categoryTotals} />
        <Card t={t}>
          <UpcomingRenewals
            t={t}
            upcomingSorted={upcomingSorted}
            selectedRenewal={selectedRenewal}
            setSelectedRenewal={setSelectedRenewal}
          />
          <SpendByCategory t={t} categoryTotals={categoryTotals} />
        </Card>
      </div>

      <Card t={t}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-[14px] font-bold">Recent Subscriptions</div>
          <span className="text-[12px] font-medium" style={{ color: t.primary }}>View all</span>
        </div>
        <SubscriptionsTable t={t} subs={filteredSubs} compact />
      </Card>

      {adding && (
        <SubscriptionForm
          t={t}
          subscription={null}
          categories={categories}
          onClose={() => setAdding(false)}
        />
      )}
    </div>
  );
}
