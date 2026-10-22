import { Outlet } from "react-router-dom";
import { NotFoundPage } from "../features/notfound";
import { useSession } from "../lib/session";

/**
 * Hides the administration screens from everyone else (they see the normal "not found" page).
 * This is a convenience only: the server enforces the ADMIN role on every admin endpoint, so
 * changing this file cannot grant anyone access.
 */
export function RequireAdmin() {
  const { state } = useSession();
  if (state.kind !== "authenticated" || state.user.role !== "ADMIN") return <NotFoundPage />;
  return <Outlet />;
}
