import { Navigate, Outlet, useLocation } from "react-router-dom";
import { SessionUnavailable } from "../features/auth";
import { useSession } from "../lib/session";

/** Layout route: everything inside needs a signed-in user. */
export function RequireAuth() {
  const { state } = useSession();
  const location = useLocation();
  if (state.kind === "loading") {
    return (
      <p role="status" className="app-status">
        Checking your session...
      </p>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="app-status">
        <SessionUnavailable message={state.message} />
      </div>
    );
  }
  if (state.kind === "anonymous") {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
