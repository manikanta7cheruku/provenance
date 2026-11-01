import { useState } from "react";
import { ActionButton, Select, TextField } from "../../../ui";
import { ACCENT_PRESETS, accentProblem } from "../contrast";
import { OPTION_LABELS } from "../labels";
import { RichField } from "../RichField";
import { ColorField, NumberField } from "./fields";
import { LayersPanel } from "./LayersPanel";
import type { Order } from "./edit";
import { LIMITS, pageSize } from "./types";
import type { CanvasDoc, CanvasElement, CanvasStyle, ShapeElement, TextElement } from "./types";
import type { StudioOptions } from "../../../lib/studio-api";

interface InspectorProps {
  doc: CanvasDoc;
  selected: CanvasElement[];
  options: StudioOptions;
  epoch: number;
  onPatch: (patch: Partial<CanvasElement>, key: string) => void;
  onBox: (patch: { x?: number; y?: number; w?: number }, key: string) => void;
  onBody: (id: string, body: TextElement["body"]) => void;
  onStyle: (patch: Partial<CanvasStyle>) => void;
  onAddPage: () => void;
  onRemovePage: (index: number) => void;
  onMoveToPage: (page: number) => void;
  selection: string[];
  onSelect: (ids: string[]) => void;
  onOrder: (ids: string[], how: Order) => void;
  onLock: (id: string, locked: boolean) => void;
}

function TextProps({ el, onPatch, onBox, onBody, epoch, doc }: { el: TextElement } & Pick<InspectorProps, "onPatch" | "onBox" | "onBody" | "epoch" | "doc">) {
  const [pw] = pageSize(doc.style);
  return (
    <>
      <TextField
        label="Name in the layers list"
        value={el.name}
        maxLength={LIMITS.maxName}
        onChange={(e) => onPatch({ name: e.target.value }, `name-${el.id}`)}
      />
      <RichField
        key={`${el.id}-${epoch}`}
        label={`Text of ${el.name}`}
        hint="Edits show on the page as you type. You can also double-click the text on the page."
        value={el.body}
        onChange={(body) => onBody(el.id, body)}
      />
      <fieldset className="cv-fields">
        <legend className="group__title">Text style</legend>
        <div className="cv-grid">
          <Select label="Font" value={el.font} onChange={(e) => onPatch({ font: e.target.value as TextElement["font"] }, `font-${el.id}`)}>
            <option value="heading">Heading font</option>
            <option value="body">Body font</option>
          </Select>
          <NumberField label="Size" unit="pt" value={el.size} min={LIMITS.sizePt[0]} max={LIMITS.sizePt[1]} step={0.5} onCommit={(size) => onPatch({ size }, `size-${el.id}`)} />
          <Select label="Alignment" value={el.align} onChange={(e) => onPatch({ align: e.target.value as TextElement["align"] }, `align-${el.id}`)}>
            <option value="left">Left</option>
            <option value="center">Center</option>
            <option value="right">Right</option>
            <option value="justify">Justified</option>
          </Select>
          <NumberField label="Line spacing" value={el.line_height} min={LIMITS.lineHeight[0]} max={LIMITS.lineHeight[1]} step={0.05} onCommit={(line_height) => onPatch({ line_height }, `lh-${el.id}`)} />
        </div>
        <ColorField label="Text color" value={el.color} onChange={(color) => onPatch({ color }, `color-${el.id}`)} />
        <label className="cv-check">
          <input type="checkbox" checked={el.caps} onChange={(e) => onPatch({ caps: e.target.checked }, `caps-${el.id}`)} />
          <span>Capital letters</span>
        </label>
      </fieldset>
      <fieldset className="cv-fields">
        <legend className="group__title">Position</legend>
        <div className="cv-grid">
          <NumberField label="Across" unit="mm" value={el.x} min={0} max={pw} disabled={el.locked} onCommit={(x) => onBox({ x }, `x-${el.id}`)} />
          <NumberField label="Down" unit="mm" value={el.y} min={0} max={400} disabled={el.locked} onCommit={(y) => onBox({ y }, `y-${el.id}`)} />
          <NumberField label="Width" unit="mm" value={el.w} min={5} max={pw} disabled={el.locked} onCommit={(w) => onBox({ w }, `w-${el.id}`)} />
        </div>
        <p className="field__hint">The height follows the text.</p>
      </fieldset>
    </>
  );
}

function ShapeProps({ el, onPatch, onBox, doc }: { el: ShapeElement } & Pick<InspectorProps, "onPatch" | "onBox" | "doc">) {
  const [pw, ph] = pageSize(doc.style);
  return (
    <>
      <TextField label="Name in the layers list" value={el.name} maxLength={LIMITS.maxName} onChange={(e) => onPatch({ name: e.target.value }, `name-${el.id}`)} />
      <fieldset className="cv-fields">
        <legend className="group__title">Shape style</legend>
        <ColorField label="Fill" allowNone value={el.fill} onChange={(fill) => onPatch({ fill }, `fill-${el.id}`)} />
        <ColorField label="Outline" allowNone value={el.stroke} onChange={(stroke) => onPatch({ stroke, stroke_pt: el.stroke_pt || 1 }, `stroke-${el.id}`)} />
        <div className="cv-grid">
          <NumberField label="Outline width" unit="pt" value={el.stroke_pt} min={0} max={12} step={0.25} onCommit={(stroke_pt) => onPatch({ stroke_pt }, `sw-${el.id}`)} />
          <NumberField label="Corner radius" unit="mm" value={el.radius} min={0} max={30} step={0.5} onCommit={(radius) => onPatch({ radius }, `radius-${el.id}`)} />
        </div>
      </fieldset>
      <fieldset className="cv-fields">
        <legend className="group__title">Position and size</legend>
        <div className="cv-grid">
          <NumberField label="Across" unit="mm" value={el.x} min={0} max={pw} disabled={el.locked} onCommit={(x) => onBox({ x }, `x-${el.id}`)} />
          <NumberField label="Down" unit="mm" value={el.y} min={0} max={ph} disabled={el.locked} onCommit={(y) => onBox({ y }, `y-${el.id}`)} />
          <NumberField label="Width" unit="mm" value={el.w} min={0.2} max={pw} step={0.5} disabled={el.locked} onCommit={(w) => onBox({ w }, `w-${el.id}`)} />
          <NumberField label="Height" unit="mm" value={el.h} min={0.2} max={ph} step={0.1} disabled={el.locked} onCommit={(h) => onPatch({ h }, `h-${el.id}`)} />
        </div>
      </fieldset>
    </>
  );
}

function PageProps({ doc, options, onStyle, onAddPage, onRemovePage, onMoveToPage, selectedCount }: Pick<InspectorProps, "doc" | "options" | "onStyle" | "onAddPage" | "onRemovePage" | "onMoveToPage"> & { selectedCount: number }) {
  const [accent, setAccent] = useState(doc.style.accent);
  const problem = accentProblem(accent);
  return (
    <>
      <fieldset className="cv-fields">
        <legend className="group__title">Page</legend>
        <div className="cv-grid">
          <Select label="Paper" value={doc.style.paper} onChange={(e) => onStyle({ paper: e.target.value })}>
            {options.papers.map((p) => (
              <option key={p} value={p}>
                {OPTION_LABELS.paper?.[p] ?? p}
              </option>
            ))}
          </Select>
          <NumberField label="Margin guide" unit="mm" value={doc.style.margin_mm} min={0} max={40} step={1} onCommit={(margin_mm) => onStyle({ margin_mm })} />
        </div>
        <Select label="Fonts" value={doc.style.font_pair} onChange={(e) => onStyle({ font_pair: e.target.value })}>
          {options.font_pairs.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}
            </option>
          ))}
        </Select>
      </fieldset>
      <fieldset className="cv-fields">
        <legend className="group__title">Accent color</legend>
        <p className="field__hint">Used wherever an element is set to Accent.</p>
        <div className="swatches" role="group" aria-label="Accent color presets">
          {ACCENT_PRESETS.map((p) => (
            <button
              key={p.value}
              type="button"
              className="swatch"
              aria-pressed={doc.style.accent === p.value}
              aria-label={p.label}
              title={p.label}
              style={{ background: p.value }}
              onClick={() => {
                setAccent(p.value);
                onStyle({ accent: p.value });
              }}
            />
          ))}
        </div>
        <TextField
          label="Custom color"
          hint="A hex code such as #1f3d7a."
          value={accent}
          error={problem ?? undefined}
          onChange={(e) => {
            const v = e.target.value.trim();
            setAccent(v);
            if (accentProblem(v) === null) onStyle({ accent: v.toLowerCase() });
          }}
        />
      </fieldset>
      <fieldset className="cv-fields">
        <legend className="group__title">Pages ({doc.pages.length} of {LIMITS.maxPages})</legend>
        <div className="group__tools">
          <ActionButton onClick={onAddPage} disabled={doc.pages.length >= LIMITS.maxPages}>
            Add a page
          </ActionButton>
        </div>
        <ul className="cv-pages">
          {doc.pages.map((page, pi) => (
            <li key={page.id}>
              <span>
                Page {pi + 1}, {page.elements.length} {page.elements.length === 1 ? "element" : "elements"}
              </span>
              <span className="group__tools">
                <ActionButton disabled={selectedCount === 0} aria-label={`Move selection here, page ${pi + 1}`} onClick={() => onMoveToPage(pi)}>
                  Move selection here
                </ActionButton>
                <ActionButton disabled={doc.pages.length <= 1} aria-label={`Remove page ${pi + 1}`} onClick={() => onRemovePage(pi)}>
                  Remove page
                </ActionButton>
              </span>
            </li>
          ))}
        </ul>
      </fieldset>
    </>
  );
}

type Tab = "element" | "layers" | "page";

function InspectorTabs({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  const items: { key: Tab; label: string }[] = [
    { key: "element", label: "Element" },
    { key: "layers", label: "Layers" },
    { key: "page", label: "Page and style" },
  ];
  return (
    <div className="cv-tabs" role="group" aria-label="Panel">
      {items.map((item) => (
        <button key={item.key} type="button" className="cv-tab" aria-pressed={tab === item.key} onClick={() => setTab(item.key)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

/** The side panel. What it shows follows the selection: one element, several, or the page itself. */
export function Inspector(props: InspectorProps) {
  const { doc, selected, onPatch } = props;
  const [tab, setTab] = useState<Tab>("element");
  const only = selected.length === 1 ? selected[0]! : null;
  let body: React.ReactNode;
  if (tab === "layers") {
    body = <LayersPanel doc={doc} selection={props.selection} onSelect={props.onSelect} onOrder={props.onOrder} onLock={props.onLock} />;
  } else if (tab === "page") {
    body = (
      <PageProps doc={doc} options={props.options} onStyle={props.onStyle} onAddPage={props.onAddPage} onRemovePage={props.onRemovePage} onMoveToPage={props.onMoveToPage} selectedCount={selected.length} />
    );
  } else if (only) {
    body = (
      <>
        <label className="cv-check">
          <input type="checkbox" checked={only.locked} onChange={(e) => onPatch({ locked: e.target.checked }, `lock-${only.id}`)} />
          <span>Locked, so it cannot be moved by accident</span>
        </label>
        {only.kind === "text" ? (
          <TextProps el={only} onPatch={onPatch} onBox={props.onBox} onBody={props.onBody} epoch={props.epoch} doc={doc} />
        ) : (
          <ShapeProps el={only} onPatch={onPatch} onBox={props.onBox} doc={doc} />
        )}
      </>
    );
  } else if (selected.length > 1) {
    body = (
      <p className="job__note">
        {selected.length} elements selected. Move them together, or use the align and distribute buttons above. Select one element to edit its text and style.
      </p>
    );
  } else {
    body = <p className="job__note">Select something on the page to edit it. Page and style has paper, fonts, colors and pages.</p>;
  }
  return (
    <aside className="cv-inspector" aria-label="Properties">
      <InspectorTabs tab={tab} setTab={setTab} />
      <div className="cv-panel">{body}</div>
    </aside>
  );
}
