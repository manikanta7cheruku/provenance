import { useEffect, useState } from "react";
import { fetchImports, isImportBusy } from "../../lib/imports-api";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { PageHeader, Section } from "../../ui";
import { AddJob } from "./AddJob";
import { RecentImports } from "./RecentImports";
import { Workbench } from "./Workbench";
import "./opportunities.css";

const REFRESH_MS = 2000;

export function OpportunitiesPage() {
  useDocumentTitle("Opportunities");
  const imports = useAsync((signal) => fetchImports(signal), []);
  const importing = imports.data?.some(isImportBusy) ?? false;
  const { reload: reloadImports } = imports;
  // Bumped when a job is added or an import ends, so the list asks again.
  const [version, setVersion] = useState(0);

  // While an import is running, keep asking. It stops by itself when the import ends.
  useEffect(() => {
    if (!importing) return;
    const timer = window.setInterval(() => {
      reloadImports();
      setVersion((v) => v + 1);
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [importing, reloadImports]);

  function onChanged() {
    reloadImports();
    setVersion((v) => v + 1);
  }

  return (
    <>
      <PageHeader
        title="Opportunities"
        description="Your jobs: what you can take, what each one asks for, and what you decided about it."
      />
      <AddJob onChanged={onChanged} />
      {imports.data ? <RecentImports batches={imports.data} /> : null}
      <Section title="Your jobs">
        <Workbench version={version} />
      </Section>
    </>
  );
}
