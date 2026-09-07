import SidebarContent from "./SidebarContent.jsx";

// Desktop-only rail. Below `md` the same content is reached through
// MobileNav.jsx, opened from the header's menu button.
export default function Sidebar({ t, dark, setDark, tab, setTab }) {
  return (
    <aside
      className="hidden md:flex flex-col justify-between shrink-0"
      style={{ width: 232, background: t.sidebar, borderRight: `1px solid ${t.border}` }}
    >
      <SidebarContent t={t} dark={dark} setDark={setDark} tab={tab} setTab={setTab} />
    </aside>
  );
}
