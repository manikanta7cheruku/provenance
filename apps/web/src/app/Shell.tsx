import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { BrandMark, Icon } from "../ui";
import type { IconName } from "../ui";
import { groupedNav, visibleNavItems, SETTINGS_ITEM } from "./nav";
import { useSession } from "../lib/session";
import { NavAccount } from "./NavAccount";
import { VerificationBanner } from "./VerificationBanner";

/** The four places people go most, for the bar at the foot of a phone. Everything else is under More. */
const TABS: { path: string; short: string; icon: IconName }[] = [
  { path: "/opportunities", short: "Jobs", icon: "briefcase" },
  { path: "/find", short: "Find", icon: "search" },
  { path: "/studio", short: "Studio", icon: "document" },
  { path: "/profile", short: "Profile", icon: "user" },
];

export function Shell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { state } = useSession();
  const user = state.kind === "authenticated" ? state.user : null;

  // Close the sheet after navigating, and when Escape is pressed.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  const groups = groupedNav([...visibleNavItems(user), SETTINGS_ITEM]);
  const wide = location.pathname.startsWith("/studio");

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <span className="topbar__brand">
          <BrandMark size={22} />
          Provenance
        </span>
        <button
          type="button"
          className="shell__scrim"
          tabIndex={-1}
          aria-hidden="true"
          data-open={menuOpen}
          onClick={() => setMenuOpen(false)}
        />
        <nav id="primary-nav" className="shell__nav" aria-label="Primary" data-open={menuOpen}>
          <span className="shell__grabber" aria-hidden="true" />
          {groups.map(({ group, items }) => (
            <div key={group} className="shell__group" data-group={group}>
              <p className="shell__group-label" aria-hidden="true">
                {group}
              </p>
              <ul className="shell__nav-list" aria-label={group}>
                {items.map((item) => (
                  <li key={item.path}>
                    <NavLink to={item.path} className="shell__link">
                      <Icon name={item.icon} size={16} />
                      <span className="shell__label">{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <NavAccount />
        </nav>
      </header>
      <main id="main" className={`shell__main${wide ? " shell__main--wide" : ""}`}>
        <VerificationBanner />
        <Outlet />
      </main>
      <nav className="tabbar" aria-label="Quick">
        {TABS.map((tab) => (
          <NavLink key={tab.path} to={tab.path} className="tabbar__link">
            <Icon name={tab.icon} size={20} />
            <span className="tabbar__label">{tab.short}</span>
          </NavLink>
        ))}
        <button
          type="button"
          className="tabbar__link"
          aria-expanded={menuOpen}
          aria-controls="primary-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <Icon name={menuOpen ? "x" : "more"} size={20} />
          <span className="tabbar__label">{menuOpen ? "Close" : "More"}</span>
        </button>
      </nav>
    </div>
  );
}
