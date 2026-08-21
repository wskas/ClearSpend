import { LayoutDashboard, CreditCard, PieChart, Settings } from "lucide-react";

export function Sidebar() {
  return (
    <aside className="w-64 bg-white border-r border-slate-200 hidden md:flex flex-col">
      <div className="p-8 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shrink-0">
          <div className="w-4 h-4 border-2 border-white rounded-sm rotate-45"></div>
        </div>
        <span className="font-bold text-xl tracking-tight">ClearSpend</span>
      </div>
      
      <nav className="flex-1 px-4 space-y-1">
        <a href="#" className="flex items-center gap-3 px-4 py-3 bg-indigo-50 text-indigo-700 rounded-xl font-medium">
          <LayoutDashboard className="w-5 h-5" /> Dashboard
        </a>
        <a href="#" className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-50 rounded-xl font-medium">
          <CreditCard className="w-5 h-5" /> Subscriptions
        </a>
        <a href="#" className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-50 rounded-xl font-medium">
          <PieChart className="w-5 h-5" /> Analytics
        </a>
        <a href="#" className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-50 rounded-xl font-medium">
          <Settings className="w-5 h-5" /> Settings
        </a>
      </nav>
      
      <div className="p-6 bg-slate-50 m-4 rounded-2xl">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Saving Goal</p>
        <p className="text-sm text-slate-600 mb-3">You saved <span className="text-indigo-600 font-bold">$42.00</span> this month by cancelling unused subs.</p>
        <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
          <div className="bg-indigo-500 h-full w-[65%]"></div>
        </div>
      </div>
    </aside>
  );
}