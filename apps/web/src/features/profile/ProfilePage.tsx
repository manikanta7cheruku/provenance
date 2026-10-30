import { useCallback, useState } from "react";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { PageHeader } from "../../ui";
import { EntriesSection } from "./EntriesSection";
import { EvidenceSection } from "./EvidenceSection";
import { PreferencesSection } from "./PreferencesSection";
import { ResumeSection } from "./ResumeSection";
import "./profile.css";

/** Your evidence base: the resume, the entries every job is compared against, and your preferences. */
export function ProfilePage() {
  useDocumentTitle("Profile");
  const [version, setVersion] = useState(0);
  const refreshEntries = useCallback(() => setVersion((value) => value + 1), []);

  return (
    <>
      <PageHeader
        title="Profile"
        description="Your evidence base: resume, projects, skills and anything else you add. Every conclusion about a job is traced back to what is stored here."
      />
      <ResumeSection onChanged={refreshEntries} />
      <EntriesSection version={version} onChanged={refreshEntries} />
      <EvidenceSection version={version} />
      <PreferencesSection />
    </>
  );
}
