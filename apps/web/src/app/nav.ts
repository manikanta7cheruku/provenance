export interface NavItem {
  path: string;
  label: string;
}

/** Single source of truth for navigation. Order is the order shown to users. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/opportunities", label: "Opportunities" },
  { path: "/saved", label: "Saved" },
  { path: "/applications", label: "Applications" },
  { path: "/profile", label: "Profile" },
  { path: "/runs", label: "Runs" },
];

export const SETTINGS_ITEM: NavItem = { path: "/settings", label: "Settings" };
