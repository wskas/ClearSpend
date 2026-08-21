import { MoreVertical } from "lucide-react";
import { subscriptions } from "../lib/mock-data";

export function SubscriptionsTable() {
  return (
    <div className="bg-white rounded-3xl border border-slate-100 p-8 shadow-sm shrink-0 mb-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-lg font-bold">Active Subscriptions</h3>
          <p className="text-sm text-slate-500 mt-1">Manage your recurring costs and categories.</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-slate-400 font-bold border-b border-slate-100">
            <tr>
              <th className="px-2 py-4">Subscription</th>
              <th className="px-2 py-4">Category</th>
              <th className="px-2 py-4 text-right">Amount</th>
              <th className="px-2 py-4">Cycle</th>
              <th className="px-2 py-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {subscriptions.map((sub) => (
              <tr key={sub.id} className="hover:bg-slate-50/50 transition-colors group">
                <td className="px-2 py-5 font-bold text-slate-900">{sub.name}</td>
                <td className="px-2 py-5">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-wider font-bold bg-indigo-50 text-indigo-600">
                    {sub.category}
                  </span>
                </td>
                <td className="px-2 py-5 text-right tabular-nums font-bold text-slate-900">${sub.amount.toFixed(2)}</td>
                <td className="px-2 py-5 text-slate-500 font-medium">{sub.cycle}</td>
                <td className="px-2 py-5 text-right">
                  <button className="text-slate-300 hover:text-slate-600 transition-colors">
                    <MoreVertical className="w-5 h-5 ml-auto" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}