import { CATEGORY_META } from "../constants/categories.js";

// Maps the Django REST API shapes onto the shape the UI components already
// expect (originally defined by the mock data). Kept as pure functions so
// useDashboardData stays the single orchestration point.

const CYCLE_LABELS = { monthly: "Monthly", yearly: "Yearly", custom: "Custom" };

// Stable fallback palette for categories that have neither a backend
// hex_color_code nor a CATEGORY_META entry, so unknown categories still get a
// consistent color instead of rendering blank.
const FALLBACK_PALETTE = ["#3457D5", "#12B3A0", "#F0A93A", "#EF5350", "#7C6AE8", "#2BD3BE"];

function fallbackColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return FALLBACK_PALETTE[hash % FALLBACK_PALETTE.length];
}

export function categoryColor(name, hex) {
  return hex || CATEGORY_META[name]?.color || fallbackColor(name || "Uncategorized");
}

export function indexBy(list, key) {
  const map = {};
  for (const item of list || []) map[item[key]] = item;
  return map;
}

// subscription id -> monthly_cost_base_currency (number). Only active subs
// appear in the projections endpoint, so inactive rows won't be present here.
export function buildMonthlyCostById(projections) {
  const map = {};
  for (const item of projections?.line_items || []) {
    map[item.id] = Number(item.monthly_cost_base_currency);
  }
  return map;
}

export function adaptSubscription(apiSub, { categoriesById, monthlyCostById }) {
  const cat = apiSub.category != null ? categoriesById[apiSub.category] : null;
  const name = cat?.name || "Uncategorized";
  return {
    id: apiSub.id,
    name: apiSub.name,
    category: name,
    // Raw category id / cycle / start date, kept so the edit form can be
    // populated without a second fetch (the display fields above are derived).
    categoryId: apiSub.category ?? "",
    billingCycle: apiSub.billing_cycle,
    startDate: apiSub.start_date || "",
    color: categoryColor(name, cat?.hex_color_code),
    amount: Number(apiSub.amount),
    currency: apiSub.original_currency,
    cycle: CYCLE_LABELS[apiSub.billing_cycle] || apiSub.billing_cycle,
    customIntervalDays: apiSub.custom_interval_days,
    renews: apiSub.next_renewal_date || null,
    active: apiSub.is_active,
    // Base-currency, FX-normalized monthly cost from the backend. null for
    // rows the projections endpoint doesn't cover (inactive subs); the
    // currency util falls back to a cycle-only estimate in that case.
    monthlyCost: monthlyCostById[apiSub.id] ?? null,
  };
}

// projections.line_items -> [{ name, value, pct, color }], sorted by spend.
export function buildCategoryTotals(projections, categoriesByName) {
  const monthlyTotal = Number(projections?.monthly_total) || 0;
  const totals = {};
  for (const item of projections?.line_items || []) {
    const name = item.category || "Uncategorized";
    totals[name] = (totals[name] || 0) + Number(item.monthly_cost_base_currency);
  }
  return Object.entries(totals)
    .map(([name, value]) => ({
      name,
      value,
      pct: monthlyTotal > 0 ? (value / monthlyTotal) * 100 : 0,
      color: categoryColor(name, categoriesByName[name]?.hex_color_code),
    }))
    .sort((a, b) => b.value - a.value);
}
