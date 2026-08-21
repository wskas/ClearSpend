export function KPICards() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 shrink-0">
      <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
        <p className="text-sm text-slate-500 font-medium mb-1">Total Monthly Spend</p>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-3xl font-bold">$2,290.00</span>
        </div>
        <p className="text-xs text-rose-500 mt-2 font-medium flex items-center">
          ↑ 4.2% from last month
        </p>
      </div>
      <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
        <p className="text-sm text-slate-500 font-medium mb-1">Projected Annual</p>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-3xl font-bold">$27,480.00</span>
        </div>
        <p className="text-xs text-emerald-500 mt-2 font-medium flex items-center">
          Optimal efficiency
        </p>
      </div>
      <div className="bg-indigo-600 p-6 rounded-3xl shadow-lg text-white">
        <p className="text-sm opacity-80 font-medium mb-1">Active Subscriptions</p>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-3xl font-bold">4</span>
        </div>
        <p className="text-xs opacity-80 mt-2 font-medium">
          Stable usage
        </p>
      </div>
    </div>
  );
}
