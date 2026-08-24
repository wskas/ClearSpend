import { useEffect, useMemo } from "react";
import { useSubscriptions, useCategories, useProjections } from "./queries.js";
import {
  adaptSubscription,
  buildCategoryTotals,
  buildMonthlyCostById,
  indexBy,
} from "../lib/adapters.js";
import { setBaseCurrency } from "../utils/currency.js";
import { daysUntil } from "../utils/dates.js";

// Central derived-state hook. Every number the UI shows (totals, category
// splits, renewal counts) is computed here so components stay presentational.
// Server state comes from TanStack Query; monetary totals come straight from
// the backend projections endpoint (already FX-normalized to base currency).
export function useDashboardData({ tab, search, statusFilter }) {
  const subsQuery = useSubscriptions();
  const catsQuery = useCategories();
  const projQuery = useProjections();

  const isLoading = subsQuery.isLoading || catsQuery.isLoading || projQuery.isLoading;
  const isError = subsQuery.isError || catsQuery.isError || projQuery.isError;

  const categories = catsQuery.data;
  const projections = projQuery.data;

  // Keep fmtMoney formatting in the user's base currency.
  useEffect(() => {
    if (projections?.base_currency) setBaseCurrency(projections.base_currency);
  }, [projections?.base_currency]);

  const subscriptions = useMemo(() => {
    const categoriesById = indexBy(categories, "id");
    const monthlyCostById = buildMonthlyCostById(projections);
    return (subsQuery.data || []).map((s) =>
      adaptSubscription(s, { categoriesById, monthlyCostById })
    );
  }, [subsQuery.data, categories, projections]);

  const activeSubs = useMemo(() => subscriptions.filter((s) => s.active), [subscriptions]);

  const monthlyTotal = useMemo(() => Number(projections?.monthly_total) || 0, [projections]);

  const categoryTotals = useMemo(() => {
    if (!projections) return [];
    return buildCategoryTotals(projections, indexBy(categories, "name"));
  }, [projections, categories]);

  // Renewal math only applies to active subs that have a start_date set.
  const withRenewal = useMemo(() => activeSubs.filter((s) => s.renews), [activeSubs]);

  const renewalsThisWeek = useMemo(
    () => withRenewal.filter((s) => daysUntil(s.renews) >= 0 && daysUntil(s.renews) <= 7),
    [withRenewal]
  );

  const nextRenewal = useMemo(
    () => [...withRenewal].sort((a, b) => daysUntil(a.renews) - daysUntil(b.renews))[0],
    [withRenewal]
  );

  const upcomingSorted = useMemo(
    () => [...withRenewal].sort((a, b) => daysUntil(a.renews) - daysUntil(b.renews)).slice(0, 7),
    [withRenewal]
  );

  const filteredSubs = useMemo(() => {
    let list = tab === "dashboard" ? activeSubs.slice(0, 5) : subscriptions;
    if (tab !== "dashboard") {
      list = list.filter((s) =>
        statusFilter === "all" ? true : statusFilter === "active" ? s.active : !s.active
      );
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) => s.name.toLowerCase().includes(q) || s.category.toLowerCase().includes(q)
      );
    }
    return list;
  }, [tab, activeSubs, subscriptions, search, statusFilter]);

  return {
    isLoading,
    isError,
    warnings: projections?.warnings || [],
    activeSubs,
    monthlyTotal,
    categoryTotals,
    renewalsThisWeek,
    nextRenewal,
    upcomingSorted,
    filteredSubs,
  };
}
