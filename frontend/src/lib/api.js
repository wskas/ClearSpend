import axios from "axios";

import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  broadcast,
  TOKENS_UPDATED,
} from "./auth.js";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Single shared instance. Import this everywhere instead of calling axios
// directly so the auth interceptors below always apply.
const api = axios.create({ baseURL });

// Endpoints that must never carry an Authorization header.
//
// DRF authenticates before it checks AllowAny, so a stale token in
// localStorage turns these into a 401 — and for the /auth/ endpoints that is
// a lockout, not an inconvenience: an expired token would block the very
// requests needed to obtain a fresh one, with clearing site data the only
// way out. All of them take their credential from the request body.
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
// The backend rotates refresh tokens and blacklists the old one. Two tabs
// whose access tokens expire together both read the same refresh token out of
// shared localStorage and both POST it; the second is a reuse. Left alone
// that logs the user out of *every* tab, because a failed refresh clears the
// shared storage the winning tab is also reading from.
//
// So: only one tab refreshes. The others wait for it and reuse the result.
// Two independent safety nets sit under this, because a lock built on
// localStorage cannot be perfectly atomic:
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
}

// Wait for the tab holding the lock to publish a new access token.
function waitForPeerRefresh(previousToken) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const check = () => {
      const current = getAccessToken();
      if (current && current !== previousToken) {
        resolve(current);
        return true;
      }
      if (!getRefreshToken()) {
        // The leader's refresh failed and it cleared storage.
        reject(new Error("Session ended in another tab"));
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

// Single-flight *within* this tab: if several requests 401 at once, they all
// await the same refresh call rather than each firing its own.
let refreshPromise = null;

function postRefresh(refresh) {
  // Bare axios (not `api`) so this call skips the interceptors and can't
  // recurse into itself on a 401.
  return axios.post(`${baseURL}/auth/token/refresh/`, { refresh }).then((res) => {
    // Backend has ROTATE_REFRESH_TOKENS=True, so a fresh refresh token comes
    // back too — persist whatever we get and tell the other tabs.
    setTokens({ access: res.data.access, refresh: res.data.refresh });
    return res.data.access;
  });
}

function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) {
    return Promise.reject(new Error("No refresh token"));
  }

  const previousToken = getAccessToken();
  const lock = acquireRefreshLock();

  if (!lock) {
    return waitForPeerRefresh(previousToken).catch(() => {
      // Peer stalled or died. Take over; the server's grace window covers
      // the case where it actually completed a moment later.
      const latest = getRefreshToken();
      if (!latest) throw new Error("No refresh token");
      return postRefresh(latest);
    });
  }

  return postRefresh(refresh).finally(() => releaseRefreshLock(lock));
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
        // Only a definitive rejection of the credential means the session is
        // over. Anything else — a 429 from the throttle, a 5xx, a dropped
        // connection — says the request failed, not that the refresh token
        // died, and discarding it there would log out a user whose
        // credentials are entirely valid.
        //
        // That is not hypothetical: the refresh endpoint sits on the shared
        // `anon` throttle bucket, so any misconfiguration that collapses
        // clients into one bucket (NUM_PROXIES too low behind a proxy) turns
        // a 429 here into a forced logout for unrelated users.
        //
        // Leaving storage intact lets the next request retry. RequireAuth
        // still bounces to /login if the token really is dead.
        const refreshStatus = refreshError?.response?.status;
        if (refreshStatus === 401 || refreshStatus === 403) {
          clearTokens();
          if (typeof window !== "undefined") {
            window.location.assign("/login");
          }
        }
        return Promise.reject(refreshError);
      });
  }
);

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

/**
 * Revoke the refresh token server-side, then clear local storage.
 *
 * The endpoint is unauthenticated by design: it takes the refresh token as
 * the credential, so this still works after the access token has expired —
 * which is the usual state of an idle tab, and precisely the case where
 * someone walking away from a shared machine needs it to work.
 *
 * Never blocks the redirect on the network call, but does await it so the
 * common path actually revokes rather than racing a page unload.
 */
export async function logout() {
  const refresh = getRefreshToken();
  if (refresh) {
    try {
      await axios.post(`${baseURL}/auth/logout/`, { refresh });
    } catch {
      // Offline, or already revoked. Clearing locally is still correct.
    }
  }
  clearTokens();
}

/** Revoke every session for this account, on every device. */
export async function logoutEverywhere() {
  try {
    await api.post("/auth/logout-all/");
  } finally {
    clearTokens();
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
