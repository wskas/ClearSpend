import { useCallback, useEffect, useState } from "react";
import { THEME } from "./theme/token.js";
import { useDashboardData } from "./hooks/useDashboardData.js";
import { useProfile } from "./hooks/queries.js";
import Sidebar from "./components/layout/Sidebar.jsx";
import MobileNav from "./components/layout/MobileNav.jsx";
import Header from "./components/layout/Header.jsx";
import DashboardPage from "./components/dashboard/DashboardPage.jsx";
import SubscriptionsPage from "./components/subscriptions/SubscriptionsPage.jsx";
import CategoriesPage from "./components/categories/CategoriesPage.jsx";

// The authenticated dashboard. Rendered behind RequireAuth by App.jsx.
export default function AppShell() {
  // Persist the theme choice so it survives refreshes (same localStorage
  // convention as the auth tokens in src/lib/auth.js).
  const [dark, setDark] = useState(() => localStorage.getItem("clearspend_theme") === "dark");
  const [tab, setTab] = useState("dashboard");
  const [navOpen, setNavOpen] = useState(false);
  const [horizon, setHorizon] = useState(6);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [showFxBanner, setShowFxBanner] = useState(true);
  const [selectedRenewal, setSelectedRenewal] = useState(null);
  const [statusFilter, setStatusFilter] = useState("active");

  const t = THEME[dark ? "dark" : "light"];

  // Stable identities: MobileNav keys its Escape listener and scroll lock on
  // `onClose`, so a fresh closure each render would tear those down and
  // rebuild them on every unrelated state change.
  const openNav = useCallback(() => setNavOpen(true), []);
  const closeNav = useCallback(() => setNavOpen(false), []);

  useEffect(() => {
    localStorage.setItem("clearspend_theme", dark ? "dark" : "light");
  }, [dark]);

  const { data: profile } = useProfile();
  const displayName = profile?.username || profile?.email || "";
  // First letters of up to two name tokens (split on spaces/@/._-), else the
  // first two characters — e.g. "Jerry Cheng" -> JC, "demo" -> DE.
  const tokens = displayName.split(/[\s@._-]+/).filter(Boolean);
  const userInitials =
    tokens.length >= 2 ? (tokens[0][0] + tokens[1][0]).toUpperCase() : displayName.slice(0, 2).toUpperCase();
  const firstName = tokens[0] || "";

  const {
    isLoading,
    isError,
    warnings,
    activeSubs,
    monthlyTotal,
    categoryTotals,
    renewalsThisWeek,
    nextRenewal,
    upcomingSorted,
    filteredSubs,
  } = useDashboardData({ tab, search, statusFilter });

  return (
    <div style={{ background: t.bg, color: t.text, fontFamily: "'Inter', sans-serif", minHeight: "100vh" }}>
      <div className="flex" style={{ minHeight: "100vh" }}>
        <Sidebar t={t} dark={dark} setDark={setDark} tab={tab} setTab={setTab} />
        <MobileNav
          t={t}
          dark={dark}
          setDark={setDark}
          tab={tab}
          setTab={setTab}
          open={navOpen}
          onClose={closeNav}
        />

        <div className="flex-1 min-w-0">
          <Header t={t} tab={tab} search={search} setSearch={setSearch} searchOpen={searchOpen} setSearchOpen={setSearchOpen} name={displayName} initials={userInitials} onOpenMenu={openNav} />

          <main className="p-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-24 text-[13px]" style={{ color: t.textMuted }}>
                Loading your dashboard…
              </div>
            ) : isError ? (
              <div className="flex items-center justify-center py-24 text-[13px]" style={{ color: t.red }}>
                Couldn't load your data. Please refresh or try again.
              </div>
            ) : (
              <>
                {tab === "dashboard" && (
                  <DashboardPage
                    t={t}
                    firstName={firstName}
                    monthlyTotal={monthlyTotal}
                    categoryTotals={categoryTotals}
                    renewalsThisWeek={renewalsThisWeek}
                    nextRenewal={nextRenewal}
                    upcomingSorted={upcomingSorted}
                    selectedRenewal={selectedRenewal}
                    setSelectedRenewal={setSelectedRenewal}
                    horizon={horizon}
                    setHorizon={setHorizon}
                    showFxBanner={showFxBanner}
                    setShowFxBanner={setShowFxBanner}
                    warnings={warnings}
                    filteredSubs={filteredSubs}
                    subsCount={activeSubs.length}
                    setTab={setTab}
                  />
                )}

                {tab === "subscriptions" && (
                  <SubscriptionsPage
                    t={t}
                    subs={filteredSubs}
                    statusFilter={statusFilter}
                    setStatusFilter={setStatusFilter}
                    search={search}
                  />
                )}

                {tab === "categories" && (
                  <CategoriesPage t={t} categoryTotals={categoryTotals} activeSubs={activeSubs} />
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
