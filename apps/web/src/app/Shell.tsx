import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { BrandMark, Button, Icon } from "../ui";
import { groupedNav, visibleNavItems, SETTINGS_ITEM } from "./nav";
import { useSession } from "../lib/session";
import { NavAccount } from "./NavAccount";
import { NavStatus } from "./NavStatus";
import { ThemeToggle } from "./ThemeToggle";
import { VerificationBanner } from "./VerificationBanner";

export function Shell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { state } = useSession();
  const user = state.kind === "authenticated" ? state.user : null;

  // Close the mobile menu after navigating, and when Escape is pressed.
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

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="shell__header">
        <span className="shell__brand">
          <BrandMark />
          Provenance
        </span>
        <Button
          className="shell__menu-button"
          aria-expanded={menuOpen}
          aria-controls="primary-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? "Close menu" : "Menu"}
        </Button>
      </header>
      <nav id="primary-nav" className="shell__nav" aria-label="Primary" data-open={menuOpen}>
        <div className="shell__groups">
          {groups.map(({ group, items }) => (
            <div key={group} className="shell__group">
              <p className="shell__group-label" aria-hidden="true">
                {group}
              </p>
              <ul className="shell__nav-list" aria-label={group}>
                {items.map((item) => (
                  <li key={item.path}>
                    <NavLink to={item.path} className="shell__link">
                      <Icon name={item.icon} />
                      <span>{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="shell__footer">
          <NavAccount />
          <div className="shell__theme">
            <ThemeToggle />
          </div>
          <div className="shell__status">
            <NavStatus />
          </div>
        </div>
      </nav>
      <main id="main" className={`shell__main${location.pathname.startsWith("/studio") ? " shell__main--wide" : ""}`}>
        <VerificationBanner />
        <Outlet />
      </main>
    </div>
  );
}
