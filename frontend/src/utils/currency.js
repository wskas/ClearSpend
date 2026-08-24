// Currency/formatting helpers. FX conversion now happens on the backend
// (ProjectionsView), so subscriptions arrive with a precomputed base-currency
// monthlyCost — these helpers only format and provide a fallback.

// 365.25 / 12 — mirrors AVG_DAYS_PER_MONTH in the backend, used to estimate a
// monthly figure for custom-interval subs the projections endpoint didn't cover.
const AVG_DAYS_PER_MONTH = 30.4375;

// The user's base currency, set once projections load. Kept as a module var so
// fmtMoney callers don't each have to thread it through.
let baseCurrency = "USD";

export function setBaseCurrency(code) {
  if (code) baseCurrency = code;
}

export function getBaseCurrency() {
  return baseCurrency;
}

export function monthlyNormalized(sub) {
  // Backend-normalized value when available (active subs).
  if (typeof sub.monthlyCost === "number") return sub.monthlyCost;

  // Fallback for rows outside the projections endpoint (e.g. inactive subs):
  // normalize the raw amount by cycle only — no FX conversion.
  const amount = Number(sub.amount) || 0;
  if (sub.cycle === "Yearly") return amount / 12;
  if (sub.cycle === "Custom" && sub.customIntervalDays) {
    return (amount / sub.customIntervalDays) * AVG_DAYS_PER_MONTH;
  }
  return amount;
}

export function fmtMoney(n, currency = baseCurrency) {
  return (Number(n) || 0).toLocaleString("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  });
}
