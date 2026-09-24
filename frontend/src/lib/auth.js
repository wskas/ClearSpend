// Session state. Nothing secret is persisted here:
//
//   - The refresh token lives in an HttpOnly cookie (`clearspend_refresh`,
//     path /api/auth/) that this code can neither read nor write. The browser
//     attaches it to the auth endpoints; the server rotates and clears it.
//   - The access token lives only in this module's memory. It is lost on
//     reload by design and re-minted from the cookie (see bootstrapSession in
//     api.js). Injected script can still use it while the tab is open, but
//     can no longer steal a credential that outlives the tab.
//
// Tabs don't share memory, so a freshly refreshed access token is handed to
// peer tabs over a BroadcastChannel instead of through localStorage.
let accessToken = null;

// Non-secret hint that a session cookie probably exists. Lets a logged-out
// visitor skip the startup refresh call, and tells a waiting tab that the
// session has ended elsewhere. Shared across tabs via localStorage; it grants
// nothing on its own -- the server only ever trusts the cookie.
const SIGNED_IN_KEY = "clearspend_signed_in";

// Where the pre-cookie build kept both tokens. Read once for migration, then
// deleted (takeLegacyRefreshToken).
const LEGACY_ACCESS_KEY = "clearspend_access";
const LEGACY_REFRESH_KEY = "clearspend_refresh";

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

export function broadcast(type, payload = {}) {
  const ch = getChannel();
  if (ch) ch.postMessage({ type, ...payload });
}

export function subscribe(handler) {
  const ch = getChannel();
  if (!ch) return () => {};
  const listener = (event) => handler(event.data?.type, event.data);
  ch.addEventListener("message", listener);
  return () => ch.removeEventListener("message", listener);
}

// localStorage can throw (private mode, blocked site data). The hint is an
// optimisation, so failures degrade to "assume there may be a session".
function readHint() {
  try {
    return localStorage.getItem(SIGNED_IN_KEY) === "1";
  } catch {
    return true;
  }
}

function writeHint(signedIn) {
  try {
    if (signedIn) localStorage.setItem(SIGNED_IN_KEY, "1");
    else localStorage.removeItem(SIGNED_IN_KEY);
  } catch {
    /* nothing useful to do */
  }
}

export function getAccessToken() {
  return accessToken;
}

export function hasSessionHint() {
  return readHint();
}

export function setAccessToken(token, { announce = true } = {}) {
  accessToken = token;
  writeHint(true);
  // Peer tabs can't read this tab's memory; hand them the token directly.
  // Anything able to listen on this channel is same-origin script, which
  // could already call refresh itself, so this exposes nothing new.
  if (announce) broadcast(TOKENS_UPDATED, { access: token });
}

export function clearSession({ announce = true } = {}) {
  accessToken = null;
  writeHint(false);
  if (announce) broadcast(TOKENS_CLEARED);
}

/**
 * One-time migration from the localStorage build: return the stored refresh
 * token (if any) and delete both legacy keys, so no token survives in
 * script-readable storage past this call.
 */
export function takeLegacyRefreshToken() {
  try {
    const refresh = localStorage.getItem(LEGACY_REFRESH_KEY);
    localStorage.removeItem(LEGACY_REFRESH_KEY);
    localStorage.removeItem(LEGACY_ACCESS_KEY);
    return refresh;
  } catch {
    return null;
  }
}

// Adopt tokens a peer tab refreshed, and drop ours when a peer logs out.
// (A BroadcastChannel never delivers a message back to its sender.)
subscribe((type, data) => {
  if (type === TOKENS_UPDATED && data?.access) accessToken = data.access;
  if (type === TOKENS_CLEARED) accessToken = null;
});
