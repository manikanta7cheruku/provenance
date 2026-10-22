import type { SessionUser } from "../lib/api";

export interface NavItem {
  path: string;
  label: string;
  /** Shown only to administrators. The server enforces the role on every admin endpoint. */
  adminOnly?: boolean;
}

/** Single source of truth for navigation. Order is the order shown to users. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/opportunities", label: "Opportunities" },
  { path: "/saved", label: "Saved" },
  { path: "/applications", label: "Applications" },
  { path: "/profile", label: "Profile" },
  { path: "/runs", label: "Runs" },
  { path: "/admin", label: "Admin", adminOnly: true },
];

export const SETTINGS_ITEM: NavItem = { path: "/settings", label: "Settings" };

/** The items a given user should see in the navigation. */
export function visibleNavItems(user: SessionUser | null): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === "ADMIN");
}
