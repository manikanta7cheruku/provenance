import { useState } from "react";
import type { ResumeContent } from "../../lib/studio-api";
import { ActionButton, ConfirmDialog, Select, TextArea, TextField } from "../../ui";
import {
  addBlock,
  addSection,
  moveBlock,
  moveSection,
  removeBlock,
  removeSection,
  setHeader,
  updateBlock,
  updateSection,
} from "./doc-ops";
import { blockLabels, KIND_LABELS } from "./labels";
import { RichField } from "./RichField";

interface ContentEditorProps {
  doc: ResumeContent;
  onChange: (next: ResumeContent) => void;
  /** Messages from the server keyed by path, such as "sections.0.blocks.1.heading". */
  problems: Record<string, string>;
  /** Changes when the whole document is replaced, so the rich text fields start again from it. */
  epoch: number;
  /** A polite announcement for screen readers after a move or a removal. */
  announce: (message: string) => void;
}

export function ContentEditor({ doc, onChange, problems, epoch, announce }: ContentEditorProps) {
  const [removing, setRemoving] = useState<number | null>(null);
  const [kind, setKind] = useState("experience");
  const kinds = Object.keys(KIND_LABELS);

  return (
    <div className="content">
      <fieldset className="group">
        <legend className="group__title">Your details</legend>
        <TextField
          label="Full name"
          value={doc.header.name}
          error={problems["header.name"]}
          autoComplete="name"
          onChange={(e) => onChange(setHeader(doc, { name: e.target.value }))}
        />
        <TextField
          label="Headline"
          hint="For example: Final year Computer Science student, data analytics."
          value={doc.header.headline}
          error={problems["header.headline"]}
          onChange={(e) => onChange(setHeader(doc, { headline: e.target.value }))}
        />
        <TextArea
          label="Contact details"
          hint="One per line: email, phone, city, links."
          rows={3}
          value={doc.header.contacts.join("\n")}
          error={problems["header.contacts"]}
          onChange={(e) =>
            onChange(setHeader(doc, { contacts: e.target.value.split("\n").slice(0, 8) }))
          }
        />
      </fieldset>

      {doc.sections.map((section, si) => {
        const labels = blockLabels(section.kind);
        const name = section.title || KIND_LABELS[section.kind] || "Section";
        return (
          <fieldset className="group" key={section.id}>
            <legend className="group__title">{name}</legend>
            <div className="group__tools">
              <ActionButton
                aria-label={`Move up, ${name}`}
                disabled={si === 0}
                onClick={() => {
                  onChange(moveSection(doc, si, -1));
                  announce(`${name} moved up to position ${si}.`);
                }}
              >
                Move up
              </ActionButton>
              <ActionButton
                aria-label={`Move down, ${name}`}
                disabled={si === doc.sections.length - 1}
                onClick={() => {
                  onChange(moveSection(doc, si, 1));
                  announce(`${name} moved down to position ${si + 2}.`);
                }}
              >
                Move down
              </ActionButton>
              <ActionButton aria-label={`Remove section, ${name}`} onClick={() => setRemoving(si)}>
                Remove section
              </ActionButton>
            </div>
            <TextField
              label="Section title"
              value={section.title}
              error={problems[`sections.${si}.title`]}
              onChange={(e) => onChange(updateSection(doc, si, { title: e.target.value }))}
            />
            {section.blocks.map((block, bi) => {
              const path = `sections.${si}.blocks.${bi}`;
              return (
                <div className="item" key={block.id}>
                  <div className="item__grid">
                    {labels.show.heading ? (
                      <TextField
                        label={labels.heading}
                        value={block.heading}
                        error={problems[`${path}.heading`]}
                        onChange={(e) => onChange(updateBlock(doc, si, bi, { heading: e.target.value }))}
                      />
                    ) : null}
                    {labels.show.subheading ? (
                      <TextField
                        label={labels.subheading}
                        value={block.subheading}
                        error={problems[`${path}.subheading`]}
                        onChange={(e) => onChange(updateBlock(doc, si, bi, { subheading: e.target.value }))}
                      />
                    ) : null}
                    {labels.show.dates ? (
                      <TextField
                        label={labels.dates}
                        value={block.dates}
                        error={problems[`${path}.dates`]}
                        onChange={(e) => onChange(updateBlock(doc, si, bi, { dates: e.target.value }))}
                      />
                    ) : null}
                    {labels.show.location ? (
                      <TextField
                        label={labels.location}
                        value={block.location}
                        error={problems[`${path}.location`]}
                        onChange={(e) => onChange(updateBlock(doc, si, bi, { location: e.target.value }))}
                      />
                    ) : null}
                  </div>
                  <RichField
                    key={`${block.id}-${epoch}`}
                    label={`${labels.body}${labels.show.heading && block.heading ? `: ${block.heading}` : ""}`}
                    hint={labels.bodyHint}
                    value={block.body}
                    onChange={(body) => onChange(updateBlock(doc, si, bi, { body }))}
                  />
                  {problems[`${path}.body`] ? <p className="field__error">{problems[`${path}.body`]}</p> : null}
                  <div className="group__tools">
                    <ActionButton
                      aria-label={`Move up, item ${bi + 1} of ${name}`}
                      disabled={bi === 0}
                      onClick={() => {
                        onChange(moveBlock(doc, si, bi, -1));
                        announce(`Item moved up to position ${bi} in ${name}.`);
                      }}
                    >
                      Move up
                    </ActionButton>
                    <ActionButton
                      aria-label={`Move down, item ${bi + 1} of ${name}`}
                      disabled={bi === section.blocks.length - 1}
                      onClick={() => {
                        onChange(moveBlock(doc, si, bi, 1));
                        announce(`Item moved down to position ${bi + 2} in ${name}.`);
                      }}
                    >
                      Move down
                    </ActionButton>
                    <ActionButton
                      aria-label={`Remove item, item ${bi + 1} of ${name}`}
                      onClick={() => {
                        onChange(removeBlock(doc, si, bi));
                        announce(`Item ${bi + 1} removed from ${name}.`);
                      }}
                    >
                      Remove item
                    </ActionButton>
                  </div>
                </div>
              );
            })}
            <ActionButton onClick={() => onChange(addBlock(doc, si))} disabled={section.blocks.length >= 30}>
              Add an item to {name}
            </ActionButton>
          </fieldset>
        );
      })}

      {problems["sections"] || problems["document"] ? (
        <p className="field__error">{problems["sections"] ?? problems["document"]}</p>
      ) : null}

      <div className="addsection">
        <Select label="Add a section" value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </Select>
        <ActionButton
          disabled={doc.sections.length >= 14}
          onClick={() => {
            onChange(addSection(doc, kind));
            announce(`${KIND_LABELS[kind]} section added at the end.`);
          }}
        >
          Add section
        </ActionButton>
      </div>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this section?"
        confirmLabel="Remove section"
        danger
        onCancel={() => setRemoving(null)}
        onConfirm={() => {
          if (removing !== null) {
            const name = doc.sections[removing]?.title || "The section";
            onChange(removeSection(doc, removing));
            announce(`${name} removed. You can restore an earlier version from the history.`);
          }
          setRemoving(null);
        }}
      >
        <p>The section and everything in it are removed from this resume. Your profile is not affected.</p>
      </ConfirmDialog>
    </div>
  );
}
