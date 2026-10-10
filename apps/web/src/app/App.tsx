import { Navigate, Route, Routes } from "react-router-dom";
import {
  ForgotPasswordPage,
  ResetPasswordPage,
  SignInPage,
  SignUpPage,
  VerifyEmailPage,
} from "../features/auth";
import { NotFoundPage } from "../features/notfound";
import { PlannedPage } from "../features/planned";
import { SettingsPage } from "../features/settings";
import { SessionProvider } from "../lib/session";
import { SystemStatusProvider } from "../lib/system-status";
import { NAV_ITEMS } from "./nav";
import { RequireAuth } from "./RequireAuth";
import { Shell } from "./Shell";

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
              {NAV_ITEMS.map((item) => (
                <Route key={item.path} path={item.path} element={<PlannedPage path={item.path} />} />
              ))}
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </SessionProvider>
    </SystemStatusProvider>
  );
}
