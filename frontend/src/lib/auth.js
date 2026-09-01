// JWT token storage. localStorage for v1 — simple and survives reloads.
// The axios client (api.js) reads/writes through these helpers; the auth
// pages call setTokens() on login and clearTokens() on logout.
//
// localStorage is shared by every tab on the origin, which is what makes the
// cross-tab coordination below necessary: one tab clearing tokens logs the
// others out too, and one tab rotating a refresh token invalidates the copy
// the others are holding.
const ACCESS_KEY = "clearspend_access";
const REFRESH_KEY = "clearspend_refresh";

// Tabs announce token changes here so peers can pick up a rotated token
// instead of racing to rotate it themselves.
export const TOKEN_CHANNEL = "clearspend_auth";
export const TOKENS_UPDATED = "tokens-updated";
export const TOKENS_CLEARED = "tokens-cleared";

let channel = null;

function getChannel() {
  // Not available in every browser (and undefined during SSR/tests). Callers
  // must treat a null channel as "coordination unavailable", not an error —
  // the server's refresh grace window is the backstop for that case.
  if (channel !== null) return channel;
  channel = typeof BroadcastChannel === "function" ? new BroadcastChannel(TOKEN_CHANNEL) : false;
  return channel;
}

export function broadcast(type) {
  const ch = getChannel();
  if (ch) ch.postMessage({ type });
}

export function subscribe(handler) {
  const ch = getChannel();
  if (!ch) return () => {};
  const listener = (event) => handler(event.data?.type);
  ch.addEventListener("message", listener);
  return () => ch.removeEventListener("message", listener);
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access, refresh }, { announce = true } = {}) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  if (announce) broadcast(TOKENS_UPDATED);
}

export function clearTokens({ announce = true } = {}) {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  if (announce) broadcast(TOKENS_CLEARED);
}

export function isAuthenticated() {
  // A refresh token is enough to render: an expired *access* token is the
  // normal steady state, and the axios interceptor renews it transparently.
  // Gating on access-token validity instead would bounce users to /login
  // every time they returned to an idle tab.
  return Boolean(getRefreshToken() || getAccessToken());
}
