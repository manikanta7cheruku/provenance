import { useState } from "react";
import type { ResumeContent, StudioOptions } from "../../lib/studio-api";
import { ActionButton, Select, TextField } from "../../ui";
import { ACCENT_PRESETS, accentProblem } from "./contrast";
import { setStyle } from "./doc-ops";
import { OPTION_LABELS } from "./labels";

interface StylePanelProps {
  doc: ResumeContent;
  options: StudioOptions;
  onChange: (next: ResumeContent) => void;
  problems: Record<string, string>;
}

export function TemplateChoice({
  options,
  value,
  onChange,
  name,
}: {
  options: StudioOptions;
  value: string;
  onChange: (key: string) => void;
  name: string;
}) {
  return (
    <fieldset className="templates">
      <legend className="group__title">Template</legend>
      <div className="templates__grid">
        {options.templates.map((template) => (
          <label className="template" key={template.key}>
            <input
              type="radio"
              name={name}
              value={template.key}
              checked={value === template.key}
              onChange={() => onChange(template.key)}
            />
            <span className="template__card">
              <span className="template__name">{template.name}</span>
              <span className="template__text">{template.description}</span>
              <span className="template__ats">
                {template.ats_safe
                  ? "Reads well in applicant tracking systems"
                  : "Design heavy: some systems may read it out of order"}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function StylePanel({ doc, options, onChange, problems }: StylePanelProps) {
  const style = doc.style;
  const [accent, setAccent] = useState(style.accent);
  const accentError = accentProblem(accent) ?? problems["style.accent"];

  function pick<K extends keyof typeof style>(key: K, value: string) {
    onChange(setStyle(doc, { [key]: value } as Partial<typeof style>));
  }

  return (
    <div className="content">
      <TemplateChoice
        options={options}
        value={style.template}
        name="template"
        onChange={(key) => pick("template", key)}
      />
      <fieldset className="group">
        <legend className="group__title">Type and spacing</legend>
        <div className="item__grid">
          <Select label="Fonts" value={style.font_pair} onChange={(e) => pick("font_pair", e.target.value)}>
            {options.font_pairs.map((pair) => (
              <option key={pair.key} value={pair.key}>
                {pair.label}
              </option>
            ))}
          </Select>
          <Select label="Text size" value={style.size} onChange={(e) => pick("size", e.target.value)}>
            {options.sizes.map((v) => (
              <option key={v} value={v}>
                {OPTION_LABELS.size?.[v] ?? v}
              </option>
            ))}
          </Select>
          <Select label="Spacing" value={style.spacing} onChange={(e) => pick("spacing", e.target.value)}>
            {options.spacings.map((v) => (
              <option key={v} value={v}>
                {OPTION_LABELS.spacing?.[v] ?? v}
              </option>
            ))}
          </Select>
          <Select label="Page margins" value={style.margins} onChange={(e) => pick("margins", e.target.value)}>
            {options.margins.map((v) => (
              <option key={v} value={v}>
                {OPTION_LABELS.margins?.[v] ?? v}
              </option>
            ))}
          </Select>
          <Select label="Lines under headings" value={style.divider} onChange={(e) => pick("divider", e.target.value)}>
            {options.dividers.map((v) => (
              <option key={v} value={v}>
                {OPTION_LABELS.divider?.[v] ?? v}
              </option>
            ))}
          </Select>
          <Select label="Paper" value={style.paper} onChange={(e) => pick("paper", e.target.value)}>
            {options.papers.map((v) => (
              <option key={v} value={v}>
                {OPTION_LABELS.paper?.[v] ?? v}
              </option>
            ))}
          </Select>
        </div>
      </fieldset>
      <fieldset className="group">
        <legend className="group__title">Accent color</legend>
        <p className="field__hint">Used for your name and headings. Only colors that are readable on white paper are accepted.</p>
        <div className="swatches" role="group" aria-label="Accent color presets">
          {ACCENT_PRESETS.map((preset) => (
            <button
              key={preset.value}
              type="button"
              className="swatch"
              aria-pressed={style.accent === preset.value}
              aria-label={preset.label}
              title={preset.label}
              style={{ background: preset.value }}
              onClick={() => {
                setAccent(preset.value);
                pick("accent", preset.value);
              }}
            />
          ))}
        </div>
        <TextField
          label="Custom color"
          hint="A hex code such as #1f3d7a."
          value={accent}
          error={accentError ?? undefined}
          onChange={(e) => {
            const value = e.target.value.trim();
            setAccent(value);
            if (accentProblem(value) === null) pick("accent", value.toLowerCase());
          }}
        />
      </fieldset>
      <ActionButton
        onClick={() => {
          const template = style.template;
          const preset = {
            classic: { font_pair: "plex-newsreader", size: "medium", spacing: "normal", margins: "normal", accent: "#222222", divider: "thin" },
            modern: { font_pair: "plex", size: "medium", spacing: "normal", margins: "normal", accent: "#1f3d7a", divider: "bold" },
            compact: { font_pair: "plex-newsreader", size: "small", spacing: "tight", margins: "narrow", accent: "#222222", divider: "thin" },
          }[template] ?? {};
          setAccent((preset as { accent?: string }).accent ?? style.accent);
          onChange(setStyle(doc, preset));
        }}
      >
        Reset style to this template
      </ActionButton>
    </div>
  );
}
