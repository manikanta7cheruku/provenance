import { Navigate, Route, Routes } from "react-router-dom";
import { SystemStatusProvider } from "../lib/system-status";
import { NotFoundPage } from "../features/notfound";
import { PlannedPage } from "../features/planned";
import { SettingsPage } from "../features/settings";
import { NAV_ITEMS } from "./nav";
import { Shell } from "./Shell";

/** Composition only: providers, routes and the shell. Screens live in features/. */
export function App() {
  return (
    <SystemStatusProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Navigate to="/opportunities" replace />} />
          {NAV_ITEMS.map((item) => (
            <Route key={item.path} path={item.path} element={<PlannedPage path={item.path} />} />
          ))}
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </SystemStatusProvider>
  );
}
