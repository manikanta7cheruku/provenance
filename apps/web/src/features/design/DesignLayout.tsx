import { NavLink, Outlet } from "react-router-dom";
import { THEME_CHOICES, useTheme } from "../../lib/theme";
import type { ThemeChoice } from "../../lib/theme";
import { Notice, SegmentedControl } from "../../ui";

const LABELS: Record<ThemeChoice, string> = { system: "System", light: "Light", dark: "Dark" };
const OPTIONS = THEME_CHOICES.map((value) => ({ value, label: LABELS[value] }));

/** Frame for the design routes. They need no sign-in and no API, so designers and CI can open them directly. */
export function DesignLayout() {
  const [theme, setTheme] = useTheme();
  return (
    <div className="design">
      <a className="skip-link" href="#design-main">
        Skip to content
      </a>
      <header className="design__header">
        <span className="design__brand">Provenance design</span>
        <nav aria-label="Design pages">
          <ul className="design__nav">
            <li>
              <NavLink to="/design" end>
                Components
              </NavLink>
            </li>
            <li>
              <NavLink to="/design/workbench">Workbench prototype</NavLink>
            </li>
            <li>
              <NavLink to="/design/job">Job detail prototype</NavLink>
            </li>
          </ul>
        </nav>
        <SegmentedControl legend="Theme" options={OPTIONS} value={theme} onChange={setTheme} />
      </header>
      <main id="design-main" className="design__main">
        <Notice tone="info">
          <p>Sample data only. Nothing on these pages is saved or sent anywhere.</p>
        </Notice>
        <Outlet />
      </main>
    </div>
  );
}
