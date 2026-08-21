import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { projectionData } from "../lib/mock-data";

export function ProjectionChart() {
  return (
    <div className="bg-white flex-1 min-h-[400px] rounded-3xl shadow-sm border border-slate-100 p-8 flex flex-col shrink-0">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h3 className="text-lg font-bold">Cost Projections</h3>
          <p className="text-sm text-slate-500 mt-1">Stacked cost analysis over 3, 6, and 12-month horizons.</p>
        </div>
        <div className="flex gap-2">
          <span className="px-3 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-700">Monthly</span>
          <span className="px-3 py-1 text-slate-400 text-xs font-bold cursor-pointer hover:text-slate-600 transition-colors">Quarterly</span>
        </div>
      </div>
      <div className="flex-1 w-full relative min-h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={projectionData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="horizon" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 'bold' }} dy={10} />
            <YAxis 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 'bold' }}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip 
              cursor={{ fill: '#f8fafc' }}
              contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', fontWeight: 'bold' }}
            />
            <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: 'bold', color: '#64748b' }} />
            <Bar dataKey="SaaS" stackId="a" fill="#4f46e5" radius={[0, 0, 4, 4]} barSize={48} />
            <Bar dataKey="Infrastructure" stackId="a" fill="#818cf8" barSize={48} />
            <Bar dataKey="Marketing" stackId="a" fill="#c7d2fe" radius={[4, 4, 0, 0]} barSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
