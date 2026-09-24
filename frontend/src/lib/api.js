import axios from "axios";

import {
  getAccessToken,
  setAccessToken,
  clearSession,
  hasSessionHint,
  takeLegacyRefreshToken,
  subscribe,
  broadcast,
  TOKENS_UPDATED,
  TOKENS_CLEARED,
} from "./auth.js";

// Same-origin by default: the refresh-token cookie is SameSite=Strict and
// CORS never grants credentials, so the API has to be reached through a
// same-site path -- Vercel's rewrite in production, Vite's dev proxy locally
// (vite.config.js). An absolute cross-origin URL here silently breaks login.
const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

// Single shared instance. Import this everywhere instead of calling axios
// directly so the auth interceptors below always apply.
const api = axios.create({ baseURL });

// Endpoints that must never carry an Authorization header.
//
// DRF authenticates before it checks AllowAny, so a stale access token turns
// these into a 401 — and for the /auth/ endpoints that is a lockout, not an
// inconvenience: an expired token would block the very requests needed to
// obtain a fresh one. Their credential is the request body (login) or the
// refresh-token cookie, never the bearer header.
//
// The backend sets authentication_classes = [] on the same endpoints; this
// is the client half of the same guarantee.
const PUBLIC_PATHS = [
  "/currencies/",
  "/auth/register/",
  "/auth/token/",      // also covers /auth/token/refresh/
  "/auth/logout/",
];
const isPublicRequest = (url = "") => PUBLIC_PATHS.some((path) => url.includes(path));

// Required by the backend on every request authenticated by the refresh
// cookie. A foreign page can't set a custom header without a CORS preflight,
// which the API never grants — this is the CSRF defence for refresh/logout.
const XHR_HEADERS = { "X-Requested-With": "XMLHttpRequest" };

// Attach the access token to every outgoing request.
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && !isPublicRequest(config.url)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Cross-tab refresh coordination
// ---------------------------------------------------------------------------
//
// The backend rotates refresh tokens and blacklists the old one. Every tab
// shares the one cookie, so two tabs whose access tokens expire together both
// present the same refresh token; the second is a reuse. Left alone that can
// log the user out of *every* tab.
//
// So: only one tab refreshes. The others wait for it and adopt the access
// token it broadcasts (auth.js). Two independent safety nets sit under this,
// because a lock built on localStorage cannot be perfectly atomic:
//   - waiters fall back to refreshing themselves if the leader goes silent
//     (a crashed or backgrounded tab must not strand the others), and
//   - the server accepts a just-rotated token for a few seconds
//     (REFRESH_REUSE_GRACE_SECONDS), which absorbs whatever slips through.

const LOCK_KEY = "clearspend_refresh_lock";
// Long enough for a slow refresh round-trip, short enough that a tab which
// dies mid-refresh doesn't block its peers for long.
const LOCK_TTL_MS = 10_000;
const WAIT_TIMEOUT_MS = 12_000;
const WAIT_POLL_MS = 150;

function acquireRefreshLock() {
  const now = Date.now();

  try {
    const held = JSON.parse(localStorage.getItem(LOCK_KEY) || "null");
    // Ignore a stale lock: whoever held it is gone or wedged.
    if (held && now - held.ts < LOCK_TTL_MS) return null;
  } catch {
    // Corrupt value — fall through and overwrite it.
  }

  const id = `${now}-${Math.random().toString(36).slice(2)}`;
  try {
    localStorage.setItem(LOCK_KEY, JSON.stringify({ id, ts: now }));
    // Re-read to settle a simultaneous write: last writer wins, and everyone
    // else sees an id that isn't theirs. Not airtight, which is exactly why
    // the server-side grace window exists.
    const confirmed = JSON.parse(localStorage.getItem(LOCK_KEY) || "null");
    return confirmed && confirmed.id === id ? id : null;
  } catch {
    // localStorage unavailable (private mode, quota). Proceed unlocked and
    // let the grace window cover it.
    return id;
  }
}

function releaseRefreshLock(id) {
  try {
    const held = JSON.parse(localStorage.getItem(LOCK_KEY) || "null");
    if (held && held.id === id) localStorage.removeItem(LOCK_KEY);
  } catch {
    /* nothing useful to do */
  }
  if (heldLockId === id) heldLockId = null;
}

function isLockHeld() {
  try {
    const held = JSON.parse(localStorage.getItem(LOCK_KEY) || "null");
    return Boolean(held && Date.now() - held.ts < LOCK_TTL_MS);
  } catch {
    return false;
  }
}

// A page unloaded mid-refresh (reload, navigation, closed tab) never reaches
// the `finally` that releases its lock. Left in place, the lock makes every
// peer — and the reloaded page itself — wait out WAIT_TIMEOUT_MS for a leader
// that no longer exists. That delay is not just slow: the unloaded page's
// refresh usually *did* reach the server and rotate the token, but the browser
// dropped the response and with it the new Set-Cookie. The old cookie is then
// only accepted inside the server's grace window (10s), which a 12s wait
// overshoots — a double reload became a logout. Releasing on pagehide lets
// the next refresh land inside the window.
let heldLockId = null;
if (typeof window !== "undefined") {
  window.addEventListener("pagehide", () => {
    if (heldLockId) releaseRefreshLock(heldLockId);
  });
}

// Wait for the tab holding the lock to broadcast a new access token.
function waitForPeerRefresh(previousToken) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const check = () => {
      const current = getAccessToken();
      if (current && current !== previousToken) {
        resolve(current);
        return true;
      }
      if (!hasSessionHint()) {
        // The leader's refresh failed definitively and it ended the session.
        reject(new Error("Session ended in another tab"));
        return true;
      }
      if (!isLockHeld()) {
        // The leader let go without handing us a token — it unloaded, or its
        // refresh failed transiently. Take over now rather than at timeout.
        reject(new Error("Leader released the lock without a token"));
        return true;
      }
      return false;
    };

    if (check()) return;

    const timer = setInterval(() => {
      if (check()) {
        clearInterval(timer);
      } else if (Date.now() - startedAt > WAIT_TIMEOUT_MS) {
        clearInterval(timer);
        // Leader never finished. Refuse to wait forever — the caller falls
        // back to refreshing itself.
        reject(new Error("Timed out waiting for peer refresh"));
      }
    }, WAIT_POLL_MS);
  });
}

// `legacyRefresh` is only ever passed by the one-time migration in
// bootstrapSession. Normally the body is empty and the browser supplies the
// cookie (same-origin, so no withCredentials needed).
function postRefresh(legacyRefresh) {
  // Bare axios (not `api`) so this call skips the interceptors and can't
  // recurse into itself on a 401.
  const body = legacyRefresh ? { refresh: legacyRefresh } : null;
  return axios
    .post(`${baseURL}/auth/token/refresh/`, body, { headers: XHR_HEADERS })
    .then((res) => {
      // The rotated refresh token arrives as a Set-Cookie. During the
      // backend's transition it is also in res.data.refresh — deliberately
      // ignored, so it never lands anywhere script can read.
      setAccessToken(res.data.access);
      return res.data.access;
    });
}

function refreshWithPeers() {
  const previousToken = getAccessToken();
  const lock = acquireRefreshLock();

  if (!lock) {
    return waitForPeerRefresh(previousToken).catch((err) => {
      // A peer ended the session: don't resurrect it.
      if (!hasSessionHint()) throw err;
      // Peer stalled or died. Take over; the server's grace window covers
      // the case where it actually completed a moment later.
      return postRefresh();
    });
  }

  heldLockId = lock;
  return postRefresh().finally(() => releaseRefreshLock(lock));
}

// Single-flight *within* this tab: if several requests 401 at once (or
// StrictMode double-runs the startup check), they all await the same refresh
// rather than each firing its own.
let refreshPromise = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = refreshWithPeers().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

// Only a definitive rejection of the credential means the session is over.
// Anything else — a 429 from the throttle, a 5xx, a dropped connection —
// says the request failed, not that the refresh token died, and ending the
// session there would log out a user whose credentials are entirely valid.
//
// That is not hypothetical: the refresh endpoint sits on the shared `anon`
// throttle bucket, so any misconfiguration that collapses clients into one
// bucket (NUM_PROXIES wrong behind a proxy) turns a 429 here into a forced
// logout for unrelated users.
const isDefinitiveAuthFailure = (err) => [401, 403].includes(err?.response?.status);

/**
 * Resolve whether this tab has a usable session, minting an access token
 * from the refresh cookie if needed. Called by RequireAuth before rendering
 * anything authenticated, since page script cannot see the cookie itself.
 *
 * Resolves true when a session exists or might (a transient failure leaves
 * the decision to the 401 interceptor on the first real request); false only
 * when there is definitively none.
 */
export function bootstrapSession() {
  // Single-flight. Callers can overlap (StrictMode runs RequireAuth's effect
  // twice in development), and a second concurrent run is wrong, not just
  // wasteful: the first has already consumed the legacy token, so the second
  // sees no token and no hint and answers "logged out" — the answer
  // RequireAuth then acts on — while the migration it raced is succeeding.
  if (!bootstrapPromise) {
    bootstrapPromise = runBootstrap().finally(() => {
      bootstrapPromise = null;
    });
  }
  return bootstrapPromise;
}

let bootstrapPromise = null;

async function runBootstrap() {
  if (getAccessToken()) return true;

  // One-time migration from the localStorage build: exchange the stored
  // refresh token for the cookie so upgrading doesn't log anyone out. The
  // backend accepts a body token while REFRESH_TOKEN_IN_BODY is on; once it
  // is off this fails with 400 and we fall through to the cookie.
  const legacy = takeLegacyRefreshToken();
  if (legacy) {
    try {
      await postRefresh(legacy);
      return true;
    } catch {
      // Expired or already rotated. The cookie may still be good (the
      // backend set one at login even for the old build), so try it next.
    }
  }

  if (!legacy && !hasSessionHint()) return false;

  try {
    await refreshAccessToken();
    return true;
  } catch (err) {
    if (isDefinitiveAuthFailure(err)) {
      clearSession();
      return false;
    }
    // A peer tab ended the session while we waited on it.
    if (!hasSessionHint()) return false;
    // Transient (offline, 5xx, 429): render, and let the 401 interceptor
    // retry on the first real request instead of bouncing a valid session.
    return true;
  }
}

function endSessionAndRedirect() {
  clearSession();
  if (typeof window !== "undefined") {
    window.location.assign("/login");
  }
}

// Another tab logged out: this tab's in-memory token is already dropped
// (auth.js), so leave the authenticated UI rather than sit on it until the
// next request fails.
subscribe((type) => {
  if (type !== TOKENS_CLEARED || typeof window === "undefined") return;
  const onAuthPage = ["/login", "/register"].includes(window.location.pathname);
  if (!onAuthPage) window.location.assign("/login");
});

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

    if (
      status !== 401 ||
      !original ||
      original._retry ||
      isAuthRequest ||
      isPublicRequest(original?.url)
    ) {
      return Promise.reject(error);
    }
    original._retry = true;

    return refreshAccessToken()
      .then((access) => {
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      })
      .catch((refreshError) => {
        // See isDefinitiveAuthFailure: anything else leaves the session
        // intact so the next request can retry.
        if (isDefinitiveAuthFailure(refreshError)) endSessionAndRedirect();
        return Promise.reject(refreshError);
      });
  }
);

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

/**
 * Revoke the refresh token server-side, then end the session locally.
 *
 * The endpoint is unauthenticated by design: the refresh cookie is the
 * credential, so this still works after the access token has expired —
 * which is the usual state of an idle tab, and precisely the case where
 * someone walking away from a shared machine needs it to work. The response
 * also deletes the cookie, which page script cannot do itself.
 *
 * Never blocks the redirect on the network call, but does await it so the
 * common path actually revokes rather than racing a page unload.
 */
export async function logout() {
  try {
    await axios.post(`${baseURL}/auth/logout/`, null, { headers: XHR_HEADERS });
  } catch {
    // Offline, or already revoked. Ending the session locally is still correct.
  }
  clearSession();
}

/** Revoke every session for this account, on every device. */
export async function logoutEverywhere() {
  try {
    await api.post("/auth/logout-all/");
  } finally {
    clearSession();
  }
}

export { broadcast, TOKENS_UPDATED };

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
