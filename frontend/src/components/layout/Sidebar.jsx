import { useState } from "react";
import { Moon, Sun, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { NAV } from "../../constants/nav.js";
import Logo from "../shared/Logo.jsx";
import { logout } from "../../lib/api.js";

export default function Sidebar({ t, dark, setDark, tab, setTab }) {
  const navigate = useNavigate();

  const [loggingOut, setLoggingOut] = useState(false);

  // Revokes the refresh token server-side before clearing it locally.
  // Without the server call, "log out" only forgets the token here -- the
  // token itself stays valid until it expires, which is the wrong outcome on
  // a shared or compromised machine.
  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  return (
    <aside
      className="hidden md:flex flex-col justify-between shrink-0"
      style={{ width: 232, background: t.sidebar, borderRight: `1px solid ${t.border}` }}
    >
      <div>
        <div className="flex items-center gap-2 px-5 pt-6 pb-2">
          <Logo size={30} />
          <span className="font-bold text-[15px]">ClearSpend</span>
        </div>

        <div className="px-5 pt-6 pb-2 text-[11px] font-semibold tracking-wide uppercase" style={{ color: t.textFaint }}>
          Menu
        </div>
        <nav className="px-3 flex flex-col gap-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            const isActive = tab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] font-medium text-left"
                style={{ background: isActive ? t.primary : "transparent", color: isActive ? "#fff" : t.textMuted }}
              >
                <Icon size={17} strokeWidth={2} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div style={{ borderTop: `1px solid ${t.border}` }}>
        <div className="px-3 pt-3">
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] font-medium text-left w-full"
            style={{ color: t.textMuted }}
          >
            <LogOut size={17} strokeWidth={2} />
            {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </div>

        <div className="px-5 py-5 flex items-center justify-between">
          <span className="flex items-center gap-2 text-[13px] font-medium" style={{ color: t.textMuted }}>
            {dark ? <Moon size={15} /> : <Sun size={15} />} Dark mode
          </span>
          <button
            onClick={() => setDark((d) => !d)}
            className="relative rounded-full"
            style={{ width: 38, height: 21, background: dark ? t.primary : "#DADEEB" }}
          >
            <span
              className="absolute rounded-full bg-white"
              style={{ width: 15, height: 15, top: 3, left: dark ? 20 : 3, transition: "left .15s ease" }}
            />
          </button>
        </div>
      </div>
    </aside>
  );
}
