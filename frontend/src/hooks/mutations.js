import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api.js";

// Write hooks for subscriptions and categories. Mutations that change spend
// also invalidate ["projections"] so dashboard totals stay in sync.

function useInvalidator(keys) {
  const qc = useQueryClient();
  return () => keys.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
}

export function useCreateSubscription() {
  const invalidate = useInvalidator(["subscriptions", "projections"]);
  return useMutation({
    mutationFn: (body) => api.post("/subscriptions/", body).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useUpdateSubscription() {
  const invalidate = useInvalidator(["subscriptions", "projections"]);
  return useMutation({
    mutationFn: ({ id, ...body }) => api.patch(`/subscriptions/${id}/`, body).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useDeleteSubscription() {
  // Backend soft-deletes (is_active=false, 200) — invalidation refreshes lists.
  const invalidate = useInvalidator(["subscriptions", "projections"]);
  return useMutation({
    mutationFn: (id) => api.delete(`/subscriptions/${id}/`).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useCreateCategory() {
  const invalidate = useInvalidator(["categories"]);
  return useMutation({
    mutationFn: (body) => api.post("/categories/", body).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useUpdateCategory() {
  // Name/color changes ripple into how subs and projections render.
  const invalidate = useInvalidator(["categories", "subscriptions", "projections"]);
  return useMutation({
    mutationFn: ({ id, ...body }) => api.patch(`/categories/${id}/`, body).then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useDeleteCategory() {
  // on_delete=SET_NULL detaches the category from its subs, so refresh those too.
  const invalidate = useInvalidator(["categories", "subscriptions", "projections"]);
  return useMutation({
    mutationFn: (id) => api.delete(`/categories/${id}/`).then((r) => r.data),
    onSuccess: invalidate,
  });
}
