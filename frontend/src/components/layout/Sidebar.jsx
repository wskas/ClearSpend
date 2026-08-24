import { Moon, Sun, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { NAV } from "../../constants/nav.js";
import { clearTokens } from "../../lib/auth.js";

export default function Sidebar({ t, dark, setDark, tab, setTab }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearTokens();
    navigate("/login", { replace: true });
  };

  return (
    <aside
      className="hidden md:flex flex-col justify-between shrink-0"
      style={{ width: 232, background: t.sidebar, borderRight: `1px solid ${t.border}` }}
    >
      <div>
        <div className="flex items-center gap-2 px-5 pt-6 pb-2">
          <div
            className="flex items-center justify-center rounded-lg cs-num"
            style={{ width: 30, height: 30, background: t.primary, color: "#fff", fontWeight: 800, fontSize: 14 }}
          >
            C
          </div>
          <span className="cs-num font-bold text-[15px]">ClearSpend</span>
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
                className="cs-tap flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] font-medium text-left"
                style={{ background: isActive ? t.primary : "transparent", color: isActive ? "#fff" : t.textMuted }}
              >
                <Icon size={17} strokeWidth={2} />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* <div className="px-5 pt-7 pb-2 text-[11px] font-semibold tracking-wide uppercase" style={{ color: t.textFaint }}>
          Help
        </div>
        <div className="px-3 flex flex-col gap-0.5">
          <div className="flex items-center gap-3 px-3 py-2.5 text-[13.5px] font-medium" style={{ color: t.textMuted }}>
            Feedback
          </div>
          <div className="flex items-center gap-3 px-3 py-2.5 text-[13.5px] font-medium" style={{ color: t.textMuted }}>
            Help Center
          </div>
        </div> */}
      </div>

      <div style={{ borderTop: `1px solid ${t.border}` }}>
        <div className="px-3 pt-3">
          <button
            onClick={handleLogout}
            className="cs-tap flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] font-medium text-left w-full"
            style={{ color: t.textMuted }}
          >
            <LogOut size={17} strokeWidth={2} />
            Log out
          </button>
        </div>

        <div className="px-5 py-5 flex items-center justify-between">
          <span className="flex items-center gap-2 text-[13px] font-medium" style={{ color: t.textMuted }}>
            {dark ? <Moon size={15} /> : <Sun size={15} />} Dark mode
          </span>
          <button
            onClick={() => setDark((d) => !d)}
            className="cs-tap relative rounded-full"
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
