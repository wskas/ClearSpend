import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getAccessToken } from "../../lib/auth.js";
import { bootstrapSession } from "../../lib/api.js";
import { THEME } from "../../theme/token.js";

// Route guard. The refresh token is an HttpOnly cookie page script can't
// see, so "is there a session?" can't be answered synchronously any more —
// on a fresh load we ask the server (bootstrapSession) before deciding.
// Redirects to /login when there's definitively no session, remembering where
// the user was headed so LoginPage can send them back after authenticating.
export default function RequireAuth({ children }) {
  const location = useLocation();
  const [status, setStatus] = useState(() => (getAccessToken() ? "ready" : "checking"));

  useEffect(() => {
    if (status !== "checking") return undefined;
    let cancelled = false;
    bootstrapSession().then((ok) => {
      if (!cancelled) setStatus(ok ? "ready" : "anonymous");
    });
    return () => {
      cancelled = true;
    };
  }, [status]);

  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (status === "checking") {
    // AppShell hasn't mounted yet, so read the persisted theme directly to
    // avoid a light flash for dark-mode users.
    const t = THEME[localStorage.getItem("clearspend_theme") === "dark" ? "dark" : "light"];
    return (
      <div
        className="flex items-center justify-center text-[13px]"
        style={{ background: t.bg, color: t.textMuted, minHeight: "100vh", fontFamily: "'Inter', sans-serif" }}
      >
        Loading…
      </div>
    );
  }

  return children;
}
