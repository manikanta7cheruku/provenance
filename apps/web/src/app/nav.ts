import type { SessionUser } from "../lib/api";
import type { IconName } from "../ui";

export interface NavItem {
  path: string;
  label: string;
  icon: IconName;
  /** Which labelled group of the navigation it sits in. */
  group: NavGroup;
  /** Shown only to administrators. The server enforces the role on every admin endpoint. */
  adminOnly?: boolean;
}

export type NavGroup = "Work" | "Build" | "System";

/** Single source of truth for navigation. Order is the order shown to users. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/opportunities", label: "Opportunities", icon: "briefcase", group: "Work" },
  { path: "/find", label: "Find jobs", icon: "search", group: "Work" },
  { path: "/saved", label: "Saved", icon: "bookmark", group: "Work" },
  { path: "/applications", label: "Applications", icon: "send", group: "Work" },
  { path: "/profile", label: "Profile", icon: "user", group: "Build" },
  { path: "/studio", label: "Resume studio", icon: "document", group: "Build" },
  { path: "/runs", label: "Runs", icon: "activity", group: "System" },
  { path: "/admin", label: "Admin", icon: "shield", group: "System", adminOnly: true },
];

export const SETTINGS_ITEM: NavItem = { path: "/settings", label: "Settings", icon: "sliders", group: "System" };

export const NAV_GROUPS: NavGroup[] = ["Work", "Build", "System"];

/** The items a given user should see in the navigation. */
export function visibleNavItems(user: SessionUser | null): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === "ADMIN");
}

/** The visible items split into their labelled groups, in order, leaving out empty groups. */
export function groupedNav(items: readonly NavItem[]): { group: NavGroup; items: NavItem[] }[] {
  return NAV_GROUPS.map((group) => ({ group, items: items.filter((item) => item.group === group) })).filter((g) => g.items.length > 0);
}
