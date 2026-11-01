import { useEffect, useId, useState } from "react";
import { SegmentedControl, Skeleton } from "../../../../ui";
import { analyzeAts } from "../ats";
import { loadFonts } from "../fonts";
import { browserMeasure } from "../measure";
import type { CanvasDoc } from "../types";
import type { TemplateContent } from "./content";
import { layoutTemplate } from "./layout";
import { PagePreview } from "./PagePreview";
import { TEMPLATES } from "./specs";
import type { TemplateSpec } from "./specs";

type Filter = "all" | "safe" | "designed";

interface Preview {
  spec: TemplateSpec;
  doc: CanvasDoc;
  safe: boolean;
}

const THUMB_PX = 168;

/** Lay every template out with the person's own words, in the browser, so the previews are real. */
function usePreviews(content: TemplateContent, paper: string): Preview[] | null {
  const [previews, setPreviews] = useState<Preview[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    setPreviews(null);
    void loadFonts().then(() => {
      if (cancelled) return;
      const { measure, dispose } = browserMeasure();
      try {
        const made = TEMPLATES.map((spec) => {
          const doc = layoutTemplate(content, spec, measure, { paper });
          return { spec, doc, safe: analyzeAts(doc).safe };
        });
        if (!cancelled) setPreviews(made);
      } finally {
        dispose();
      }
    });
    return () => {
      cancelled = true;
    };
  }, [content, paper]);
  return previews;
}

interface GalleryProps {
  content: TemplateContent;
  paper: string;
  value: string;
  onChange: (spec: TemplateSpec) => void;
  legend?: string;
}

/** The template library as a group of radio cards: pick one, see it with your own words. */
export function TemplateGallery({ content, paper, value, onChange, legend = "Template" }: GalleryProps) {
  const name = useId();
  const [filter, setFilter] = useState<Filter>("all");
  const previews = usePreviews(content, paper);
  if (!previews) return <Skeleton label="Laying the templates out with your words" lines={4} />;
  const shown = previews.filter((p) => filter === "all" || (filter === "safe" ? p.safe : !p.safe));
  return (
    <div className="tpl">
      <SegmentedControl<Filter>
        legend="Show"
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: `All ${previews.length}` },
          { value: "safe", label: "ATS-safe" },
          { value: "designed", label: "Designed" },
        ]}
      />
      <p className="field__hint">
        ATS-safe means one column of plain text that applicant tracking systems read in order. Designed layouts use columns, bands or panels and look more
        distinctive, and some systems read them less reliably. Everything can be changed after you pick.
      </p>
      <fieldset className="tpl__group">
        <legend className="group__title">{legend}</legend>
        <ul className="tpl__grid">
          {shown.map(({ spec, doc, safe }) => (
            <li key={spec.id}>
              <label className="tpl-card">
                <PagePreview doc={doc} width={THUMB_PX} />
                <span className="tpl-card__head">
                  <input type="radio" className="tpl-card__input" name={name} value={spec.id} checked={value === spec.id} onChange={() => onChange(spec)} />
                  <span className="tpl-card__name">{spec.name}</span>
                </span>
                <span className="tpl-card__meta">{spec.tags.join(", ")}</span>
                <span className={`tpl-card__badge${safe ? " is-safe" : ""}`}>{safe ? "ATS-safe" : "Designed layout"}</span>
                <span className="tpl-card__text">{spec.description}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
    </div>
  );
}
