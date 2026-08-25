import { useState } from "react";
import { Plus } from "lucide-react";
import CategoryCard from "./CategoryCard.jsx";
import CategoryForm from "./CategoryForm.jsx";
import { useCategories } from "../../hooks/queries.js";
import { useDeleteCategory } from "../../hooks/mutations.js";

export default function CategoriesPage({ t, categoryTotals, activeSubs }) {
  const { data: categories = [] } = useCategories();
  const deleteM = useDeleteCategory();
  // undefined = closed, null = creating, object = editing.
  const [editing, setEditing] = useState(undefined);

  // Spend/pct come from the projections-derived totals, keyed by name.
  const totalsByName = Object.fromEntries(categoryTotals.map((c) => [c.name, c]));

  const handleDelete = (cat) => {
    if (window.confirm(`Delete "${cat.name}"? Its subscriptions will become uncategorized.`)) {
      deleteM.mutate(cat.id);
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {categories.map((cat) => {
        const totals = totalsByName[cat.name];
        const count = activeSubs.filter((s) => s.category === cat.name).length;
        return (
          <CategoryCard
            key={cat.id}
            t={t}
            category={cat}
            count={count}
            value={totals?.value ?? 0}
            pct={totals?.pct ?? 0}
            onEdit={() => setEditing(cat)}
            onDelete={() => handleDelete(cat)}
          />
        );
      })}

      <button
        onClick={() => setEditing(null)}
        className="rounded-2xl p-5 flex flex-col items-center justify-center gap-2"
        style={{ background: t.card, border: `1px dashed ${t.border}`, boxShadow: t.shadow }}
      >
        <span
          className="flex items-center justify-center rounded-full"
          style={{ width: 36, height: 36, background: t.primarySoft, color: t.primary }}
        >
          <Plus size={16} />
        </span>
        <span className="text-[12.5px] font-medium" style={{ color: t.textMuted }}>Add category</span>
      </button>

      {editing !== undefined && (
        <CategoryForm t={t} category={editing} onClose={() => setEditing(undefined)} />
      )}
    </div>
  );
}
