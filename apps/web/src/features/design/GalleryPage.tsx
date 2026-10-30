import { useState } from "react";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  ActionButton,
  Button,
  Checkbox,
  ConfirmDialog,
  DataTable,
  EmptyState,
  FileDrop,
  Notice,
  PageHeader,
  Section,
  SegmentedControl,
  Select,
  Skeleton,
  Status,
  TextArea,
  TextField,
} from "../../ui";

const SWATCHES = [
  "--color-surface-base",
  "--color-surface-raised",
  "--color-surface-sunken",
  "--color-border-subtle",
  "--color-border-control",
  "--color-text-primary",
  "--color-text-secondary",
  "--color-accent",
  "--color-accent-subtle",
  "--color-success",
  "--color-warning",
  "--color-danger",
  "--color-info",
];

const TYPE_SCALE = [
  { name: "Heading", token: "text-heading", family: "Newsreader", className: "type--heading" },
  { name: "Title", token: "text-title", family: "Newsreader", className: "type--title" },
  { name: "Section", token: "text-body-lg", family: "IBM Plex Sans, semibold", className: "type--section" },
  { name: "Body", token: "text-body", family: "IBM Plex Sans", className: "type--body" },
  { name: "Small", token: "text-small", family: "IBM Plex Sans", className: "type--small" },
  { name: "Caption", token: "text-caption", family: "IBM Plex Sans, uppercase", className: "type--caption" },
  { name: "Data", token: "font-mono", family: "IBM Plex Mono", className: "type--mono" },
];

const THEME_OPTIONS = [
  { value: "one", label: "First" },
  { value: "two", label: "Second" },
  { value: "three", label: "Third" },
] as const;

/** The component gallery: every primitive in every state, in the active theme. Axe scans this page in CI. */
export function GalleryPage() {
  useDocumentTitle("Design system");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [segment, setSegment] = useState<"one" | "two" | "three">("one");
  const [file, setFile] = useState<{ name: string; size: number } | null>(null);
  const [fileError, setFileError] = useState<string | undefined>(undefined);

  return (
    <>
      <PageHeader
        title="Design system"
        description="Every primitive in every state. Switch the theme in the header to check both."
      />

      <Section title="Color roles">
        <ul className="swatches">
          {SWATCHES.map((token) => (
            <li key={token} className="swatch">
              <span className="swatch__chip" style={{ background: `var(${token})` }} aria-hidden="true" />
              <code>{token.replace("--color-", "")}</code>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Type scale">
        <ul className="type-scale">
          {TYPE_SCALE.map((row) => (
            <li key={row.name}>
              <span className={row.className}>The quick brown fox, 0123456789</span>
              <span className="type-scale__meta">
                {`${row.name} · ${row.token} · ${row.family}`}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Buttons">
        <div className="row">
          <Button variant="primary">Primary</Button>
          <Button>Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button disabled>Disabled</Button>
          <Button variant="primary" busy>
            Saving
          </Button>
        </div>
        <div className="row">
          <ActionButton variant="primary">Action primary</ActionButton>
          <ActionButton>Action</ActionButton>
          <ActionButton variant="danger">Action danger</ActionButton>
          <ActionButton disabled>Action disabled</ActionButton>
        </div>
      </Section>

      <Section title="Status">
        <div className="row">
          <Status tone="ok" label="Completed" />
          <Status tone="warn" label="Waiting for you" />
          <Status tone="danger" label="Failed" />
          <Status tone="neutral" label="Queued" />
        </div>
        <p className="note">The dot shape differs by tone and the text carries the meaning. Color is never the only signal.</p>
      </Section>

      <Section title="Notices">
        <Notice tone="info" title="Information">
          <p>A neutral message with a leading rule, not a box.</p>
        </Notice>
        <Notice tone="warn" title="Needs attention">
          <p>Something to check before you continue.</p>
        </Notice>
        <Notice tone="danger" title="Something went wrong">
          <p>Your data is safe. Try again, or contact support with the request id.</p>
        </Notice>
      </Section>

      <Section title="Form controls">
        <div className="form-narrow">
          <TextField label="Text field" hint="Help appears before the user types." />
          <TextField label="Invalid field" defaultValue="not-an-email" error="Enter an email address like name@example.com." />
          <TextField label="Disabled field" disabled defaultValue="Read only for now" />
          <TextArea label="Multiline" hint="For longer answers." rows={3} />
          <Select label="Select" defaultValue="b">
            <option value="a">Option A</option>
            <option value="b">Option B</option>
          </Select>
          <Checkbox label="Checkbox" hint="Use for a yes or no choice." />
          <Checkbox label="Checkbox with an error" error="You must agree to continue." />
        </div>
        <div className="row">
          <SegmentedControl legend="Segmented control" showLegend options={THEME_OPTIONS} value={segment} onChange={setSegment} />
        </div>
      </Section>

      <Section title="File drop">
        <div className="form-narrow">
          <FileDrop
            label="Resume"
            hint="PDF or DOCX, up to 5 MB. Checked again on the server."
            extensions={[".pdf", ".docx"]}
            maxBytes={5 * 1024 * 1024}
            file={file}
            error={fileError}
            onSelect={(chosen) => {
              setFile({ name: chosen.name, size: chosen.size });
              setFileError(undefined);
            }}
            onReject={(message) => {
              setFile(null);
              setFileError(message);
            }}
          />
        </div>
      </Section>

      <Section title="Table">
        <DataTable caption="Table with a selected row">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">State</th>
              <th scope="col" className="num">
                Count
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">First row</th>
              <td>
                <Status tone="ok" label="Completed" />
              </td>
              <td className="num">12</td>
            </tr>
            <tr aria-current="true">
              <th scope="row">Selected row</th>
              <td>
                <Status tone="warn" label="Waiting for you" />
              </td>
              <td className="num">8</td>
            </tr>
            <tr>
              <th scope="row">Third row</th>
              <td>
                <Status tone="neutral" label="Queued" />
              </td>
              <td className="num">3</td>
            </tr>
          </tbody>
        </DataTable>
      </Section>

      <Section title="Dialog">
        <ActionButton onClick={() => setConfirmOpen(true)}>Open a confirmation</ActionButton>
        <ConfirmDialog
          open={confirmOpen}
          title="Delete this resume?"
          confirmLabel="Delete resume"
          danger
          onCancel={() => setConfirmOpen(false)}
          onConfirm={() => setConfirmOpen(false)}
        >
          <p>The file and its stored copy are removed. Your profile entries are kept.</p>
        </ConfirmDialog>
      </Section>

      <Section title="Loading and empty">
        <Skeleton label="Loading the example list" lines={4} />
        <div className="gap-top">
          <EmptyState
            title="Nothing here yet"
            why="Explain what this area is for and why it matters."
            next="Say the one thing the user can do next."
          />
        </div>
      </Section>
    </>
  );
}
