import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { EmptyState, PageHeader } from "../../ui";
import { PLANNED_SCREENS } from "./planned-screens";

/** Honest placeholder for a screen that a later checkpoint builds. */
export function PlannedPage({ path }: { path: string }) {
  const screen = PLANNED_SCREENS[path];
  if (!screen) throw new Error(`No planned screen is defined for ${path}`);
  useDocumentTitle(screen.title);
  return (
    <>
      <PageHeader title={screen.title} description={screen.description} />
      <EmptyState title={`${screen.title} is not built yet`} why={screen.why} next={screen.next} />
    </>
  );
}
