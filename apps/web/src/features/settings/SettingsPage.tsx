import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { PageHeader, Section } from "../../ui";
import { SystemStatusPanel } from "./SystemStatusPanel";

// Account, usage and connection sections are added here by later checkpoints.
export function SettingsPage() {
  useDocumentTitle("Settings");
  return (
    <>
      <PageHeader
        title="Settings"
        description="Account controls arrive with sign-in in checkpoint 1.2. System status is live now."
      />
      <Section title="System status">
        <SystemStatusPanel />
      </Section>
    </>
  );
}
