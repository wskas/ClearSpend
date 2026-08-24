import { useQuery } from "@tanstack/react-query";
import api from "../lib/api.js";

// Raw server-state hooks. Components/derived-state read through these; the
// axios client attaches auth and handles token refresh transparently.

export function useSubscriptions() {
  return useQuery({
    queryKey: ["subscriptions"],
    queryFn: async () => (await api.get("/subscriptions/")).data,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/categories/")).data,
  });
}

export function useProjections() {
  return useQuery({
    queryKey: ["projections"],
    queryFn: async () => (await api.get("/analytics/projections/")).data,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/user/profile/")).data,
  });
}
