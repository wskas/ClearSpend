import { Search, Bell, X, Menu } from "lucide-react";

export default function Header({ t, tab, search, setSearch, searchOpen, setSearchOpen, name, initials, onOpenMenu }) {
  return (
    <header className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.border}` }}>
      <div className="flex items-center gap-3 min-w-0">
        {/* The sidebar is hidden below `md`, so this is the only way into the
            other tabs on a phone. */}
        <button
          onClick={onOpenMenu}
          aria-label="Open menu"
          className="md:hidden flex items-center justify-center rounded-lg shrink-0"
          style={{ width: 34, height: 34, border: `1px solid ${t.border}` }}
        >
          <Menu size={16} style={{ color: t.textMuted }} />
        </button>
        <h1 className="text-[17px] font-bold capitalize truncate">{tab}</h1>
      </div>
      <div className="flex items-center gap-3">
        {searchOpen ? (
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-1.5"
            style={{ background: t.cardAlt, border: `1px solid ${t.border}` }}
          >
            <Search size={15} style={{ color: t.textMuted }} />
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onBlur={() => !search && setSearchOpen(false)}
              placeholder="Search subscriptions..."
              className="bg-transparent outline-none text-[13px] w-40"
              style={{ color: t.text }}
            />
            {search && (
              <button onClick={() => { setSearch(""); setSearchOpen(false); }}>
                <X size={13} style={{ color: t.textMuted }} />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center justify-center rounded-lg"
            style={{ width: 34, height: 34, border: `1px solid ${t.border}` }}
          >
            <Search size={15} style={{ color: t.textMuted }} />
          </button>
        )}
        {/* <button
          className="relative flex items-center justify-center rounded-lg"
          style={{ width: 34, height: 34, border: `1px solid ${t.border}` }}
        >
          <Bell size={15} style={{ color: t.textMuted }} />
          <span className="absolute rounded-full" style={{ width: 7, height: 7, top: 7, right: 8, background: t.red }} />
        </button> */}
        <div className="flex items-center gap-2 pl-2" style={{ borderLeft: `1px solid ${t.border}` }}>
          <div
            className="rounded-full flex items-center justify-center font-bold text-[11px]"
            style={{ width: 30, height: 30, background: t.primarySoft, color: t.primary }}
          >
            {initials || "…"}
          </div>
          <div className="hidden sm:block leading-tight">
            <div className="text-[13px] font-semibold">{name || "…"}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
