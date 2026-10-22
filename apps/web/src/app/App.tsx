import { Navigate, Route, Routes } from "react-router-dom";
import {
  AdminLayout,
  AuditPage,
  InvitesPage,
  SystemPage,
  UserPage,
  UsersPage,
} from "../features/admin";
import {
  ForgotPasswordPage,
  ResetPasswordPage,
  SignInPage,
  SignUpPage,
  VerifyEmailPage,
} from "../features/auth";
import { NotFoundPage } from "../features/notfound";
import { PlannedPage } from "../features/planned";
import { RunDetailPage, RunsPage } from "../features/runs";
import { SettingsPage } from "../features/settings";
import { SessionProvider } from "../lib/session";
import { SystemStatusProvider } from "../lib/system-status";
import { NAV_ITEMS } from "./nav";
import { RequireAdmin } from "./RequireAdmin";
import { RequireAuth } from "./RequireAuth";
import { Shell } from "./Shell";

/** Screens that are built. Everything else in the navigation still shows a "planned" page. */
const BUILT_PATHS = new Set(["/runs", "/admin"]);

/** Composition only: providers, routes and the shell. Screens live in features/. */
export function App() {
  return (
    <SystemStatusProvider>
      <SessionProvider>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/signup" element={<SignUpPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<Shell />}>
              <Route index element={<Navigate to="/opportunities" replace />} />
              {NAV_ITEMS.filter((item) => !BUILT_PATHS.has(item.path)).map((item) => (
                <Route key={item.path} path={item.path} element={<PlannedPage path={item.path} />} />
              ))}
              <Route path="/runs" element={<RunsPage />} />
              <Route path="/runs/:runId" element={<RunDetailPage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/admin" element={<AdminLayout />}>
                  <Route index element={<SystemPage />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="users/:userId" element={<UserPage />} />
                  <Route path="invites" element={<InvitesPage />} />
                  <Route path="audit" element={<AuditPage />} />
                </Route>
              </Route>
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </SessionProvider>
    </SystemStatusProvider>
  );
}
