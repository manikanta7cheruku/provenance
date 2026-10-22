import { NavLink, Outlet } from "react-router-dom";
import "./admin.css";

const LINKS = [
  { to: "/admin", label: "System", end: true },
  { to: "/admin/users", label: "Users", end: false },
  { to: "/admin/invites", label: "Invites", end: false },
  { to: "/admin/audit", label: "Audit log", end: false },
];

/** Shell for the administration screens. The server enforces the ADMIN role on every call. */
export function AdminLayout() {
  return (
    <div className="admin">
      <nav className="admin__nav" aria-label="Administration">
        {LINKS.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            {link.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
