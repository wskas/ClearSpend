import axios from "axios";

import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from "./auth.js";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Single shared instance. Import this everywhere instead of calling axios
// directly so the auth interceptors below always apply.
const api = axios.create({ baseURL });

// Attach the access token to every outgoing request.
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single-flight refresh: if several requests 401 at once, they all await the
// same refresh call rather than each firing its own.
let refreshPromise = null;

function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) {
    return Promise.reject(new Error("No refresh token"));
  }
  // Bare axios (not `api`) so this call skips the interceptors and can't
  // recurse into itself on a 401.
  return axios
    .post(`${baseURL}/auth/token/refresh/`, { refresh })
    .then((res) => {
      // Backend has ROTATE_REFRESH_TOKENS=True, so a fresh refresh token
      // comes back too — persist whatever we get.
      setTokens({ access: res.data.access, refresh: res.data.refresh });
      return res.data.access;
    });
}

// On 401, try to refresh once and replay the original request.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const original = error.config;
    const status = error.response?.status;

    // A 401 from an auth endpoint means bad/expired credentials on the login
    // or refresh call itself — not an expired access token. Let it propagate
    // so the auth pages can show the error, instead of trying to refresh
    // (which has nothing to refresh) and reloading to /login.
    const isAuthRequest = original?.url?.includes("/auth/");

    if (status !== 401 || !original || original._retry || isAuthRequest) {
      return Promise.reject(error);
    }
    original._retry = true;

    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }

    return refreshPromise
      .then((access) => {
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      })
      .catch((refreshError) => {
        // Refresh failed (expired/blacklisted) — drop tokens and bounce to
        // login. The route guard (Phase 2) will also enforce this on render.
        clearTokens();
        if (typeof window !== "undefined") {
          window.location.assign("/login");
        }
        return Promise.reject(refreshError);
      });
  }
);

// Pull a human-readable message out of a DRF error response. Handles the
// common shapes: a plain string, {detail: "..."}, or field-keyed
// {field: ["msg", ...]} — returns the first message it finds.
export function getErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  const data = error?.response?.data;
  if (!data) return error?.message || fallback;
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;

  const firstKey = Object.keys(data)[0];
  if (!firstKey) return fallback;
  const value = data[firstKey];
  const message = Array.isArray(value) ? value[0] : value;
  return message ? String(message) : fallback;
}

// Map a DRF field-keyed error response ({field: ["msg"]}) to a flat
// {field: "msg"} object suitable for Formik's setErrors.
export function getFieldErrors(error) {
  const data = error?.response?.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  const out = {};
  for (const [key, value] of Object.entries(data)) {
    out[key] = Array.isArray(value) ? value[0] : String(value);
  }
  return out;
}

export default api;
