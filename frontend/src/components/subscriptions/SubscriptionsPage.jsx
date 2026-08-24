import { useState } from "react";
import { Plus } from "lucide-react";
import Card from "../shared/Card.jsx";
import SubscriptionsTable from "./SubscriptionsTable.jsx";
import SubscriptionForm from "./SubscriptionForm.jsx";
import { useCategories } from "../../hooks/queries.js";
import { useDeleteSubscription } from "../../hooks/mutations.js";

const FILTERS = ["active", "inactive", "all"];

export default function SubscriptionsPage({ t, subs, statusFilter, setStatusFilter, search }) {
  const { data: categories = [] } = useCategories();
  const deleteM = useDeleteSubscription();
  // undefined = closed, null = creating, object = editing that subscription.
  const [editing, setEditing] = useState(undefined);

  const handleDelete = (sub) => {
    if (window.confirm(`Delete "${sub.name}"? It will be marked inactive.`)) {
      deleteM.mutate(sub.id);
    }
  };

  return (
    <Card t={t}>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <div className="text-[15px] font-bold">All Subscriptions</div>
          <div className="text-[12px]" style={{ color: t.textMuted }}>
            {search && ` — filtered by "${search}"`}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg p-0.5" style={{ background: t.cardAlt, border: `1px solid ${t.border}` }}>
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className="cs-tap rounded-md px-3 py-1.5 text-[12px] font-semibold capitalize"
                style={{ background: statusFilter === f ? t.primary : "transparent", color: statusFilter === f ? "#fff" : t.textMuted }}
              >
                {f}
              </button>
            ))}
          </div>
          <button
            onClick={() => setEditing(null)}
            className="cs-tap flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white"
            style={{ background: t.primary }}
          >
            <Plus size={14} /> Add
          </button>
        </div>
      </div>

      <SubscriptionsTable t={t} subs={subs} onEdit={setEditing} onDelete={handleDelete} />

      {editing !== undefined && (
        <SubscriptionForm
          t={t}
          subscription={editing}
          categories={categories}
          onClose={() => setEditing(undefined)}
        />
      )}
    </Card>
  );
}
