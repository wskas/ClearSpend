// JWT token storage. localStorage for v1 — simple and survives reloads.
// The axios client (api.js) reads/writes through these helpers; the auth
// pages (Phase 2) call setTokens() on login and clearTokens() on logout.
const ACCESS_KEY = "clearspend_access";
const REFRESH_KEY = "clearspend_refresh";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated() {
  return Boolean(getAccessToken());
}
