import { useQuery } from "@tanstack/react-query";
import api from "../lib/api.js";

// Raw server-state hooks. Components/derived-state read through these; the
// axios client attaches auth and handles token refresh transparently.

// List endpoints are paginated ({count, next, previous, results}). Hooks
// return a plain array either way so callers never branch on the envelope.
//
// This is safe for the dashboard only because its headline figures do not
// come from these lists: totals are computed server-side by
// /analytics/projections/ over the user's full active set. If an aggregate
// ever starts being derived from useSubscriptions(), a page boundary would
// silently make it wrong rather than merely short.
const unwrap = (data) => (Array.isArray(data) ? data : data?.results ?? []);

// Deliberately above the backend's MAX_SUBSCRIPTIONS_PER_USER cap, so the
// dashboard sees every row in one request while the endpoint still refuses
// to serve an unbounded set.
const LIST_PAGE_SIZE = 500;

export function useSubscriptions() {
  return useQuery({
    queryKey: ["subscriptions"],
    queryFn: async () =>
      unwrap((await api.get("/subscriptions/", { params: { page_size: LIST_PAGE_SIZE } })).data),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () =>
      unwrap((await api.get("/categories/", { params: { page_size: LIST_PAGE_SIZE } })).data),
  });
}

export function useProjections() {
  return useQuery({
    queryKey: ["projections"],
    queryFn: async () => (await api.get("/analytics/projections/")).data,
  });
}

// Last-resort list for when /currencies/ is unreachable (backend down, network
// blip). This is NOT a second source of truth — whenever the request succeeds
// the backend's list wins. It exists so the signup form still offers real
// choices instead of silently collapsing to a single option.
export const FALLBACK_CURRENCIES = [
  "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "SGD", "IDR", "HKD",
];

// The canonical currency list lives in the backend (subscriptions/constants.py)
// so the dropdowns can't drift from what fetch_exchange_rates actually syncs.
// Public endpoint: the register form needs it before the user has a token.
export function useCurrencies() {
  return useQuery({
    queryKey: ["currencies"],
    queryFn: async () => (await api.get("/currencies/")).data.currencies,
    staleTime: Infinity,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/user/profile/")).data,
  });
}
