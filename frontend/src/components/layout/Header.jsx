import { Plus } from "lucide-react";

export function Header() {
  return (
    <header className="h-20 bg-white border-b border-slate-200 flex items-center justify-between px-10 shrink-0">
      <h2 className="text-2xl font-bold">Overview</h2>
      <div className="flex items-center gap-4">
        <button className="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-bold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm">
          <Plus className="w-4 h-4" />
          Add Subscription
        </button>
      </div>
    </header>
  );
}
