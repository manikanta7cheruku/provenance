import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { PageHeader, Section } from "../../ui";
import { AccountSection } from "./AccountSection";
import { ShortlistSection } from "./ShortlistSection";
import { SystemStatusPanel } from "./SystemStatusPanel";

// Usage and connection sections are added here by later checkpoints.
export function SettingsPage() {
  useDocumentTitle("Settings");
  return (
    <>
      <PageHeader title="Settings" description="Your account, your shortlist email and the state of the system." />
      <AccountSection />
      <ShortlistSection />
      <Section title="System status">
        <SystemStatusPanel />
      </Section>
    </>
  );
}
