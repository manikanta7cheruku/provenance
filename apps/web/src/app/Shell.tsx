import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Button } from "../ui";
import { NAV_ITEMS, SETTINGS_ITEM } from "./nav";
import { NavStatus } from "./NavStatus";

export function Shell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

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

  const links = [...NAV_ITEMS, SETTINGS_ITEM];

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="shell__header">
        <span className="shell__brand">Provenance</span>
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
        <ul className="shell__nav-list">
          {links.map((item) => (
            <li key={item.path}>
              <NavLink to={item.path} className="shell__link">
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="shell__status">
          <NavStatus />
        </div>
      </nav>
      <main id="main" className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}
