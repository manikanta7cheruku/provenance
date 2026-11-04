import { useState } from "react";
import { SegmentedControl, Section } from "../../ui";
import { ImportFileForm } from "./ImportFileForm";
import { ImportUrlForm } from "./ImportUrlForm";
import { ManualJobForm } from "./ManualJobForm";
import { PasteJobForm } from "./PasteJobForm";

type Way = "paste" | "type" | "link" | "file";

const WAYS = [
  { value: "paste", label: "Paste text" },
  { value: "type", label: "Type it in" },
  { value: "link", label: "From a link" },
  { value: "file", label: "From a spreadsheet" },
] as const;

/** The four ways a job gets here. All of them end as a private posting that is read the same way. */
export function AddJob({ onChanged }: { onChanged: () => void }) {
  const [way, setWay] = useState<Way>("paste");
  return (
    <Section title="Add a job">
      <SegmentedControl legend="How do you want to add a job?" options={WAYS} value={way} onChange={setWay} />
      <div className="jobs__way">
        {way === "paste" ? <PasteJobForm onPasted={onChanged} /> : null}
        {way === "type" ? <ManualJobForm onAdded={onChanged} /> : null}
        {way === "link" ? <ImportUrlForm onStarted={onChanged} /> : null}
        {way === "file" ? <ImportFileForm onStarted={onChanged} /> : null}
      </div>
    </Section>
  );
}
