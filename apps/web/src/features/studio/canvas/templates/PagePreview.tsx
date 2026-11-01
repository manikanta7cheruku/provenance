import { elementCss, reactStyle } from "../css";
import { RichView } from "../rich";
import { pageSize } from "../types";
import type { CanvasDoc } from "../types";

const PX_PER_MM = 96 / 25.4;

/**
 * The first page of a canvas document, drawn small and read-only. Used for the template gallery.
 * It draws the same elements with the same CSS as the editor, scaled down.
 */
export function PagePreview({ doc, width }: { doc: CanvasDoc; width: number }) {
  const [pw, ph] = pageSize(doc.style);
  const scale = width / (pw * PX_PER_MM);
  const page = doc.pages[0];
  return (
    <div className="tpl-thumb" aria-hidden="true" style={{ width, height: ph * PX_PER_MM * scale }}>
      <div className="cv-page tpl-page" style={{ width: `${pw}mm`, height: `${ph}mm`, transform: `scale(${scale})` }}>
        {page?.elements.map((el, index) => {
          const style = reactStyle(elementCss(el, doc.style, index + 1));
          if (el.kind === "shape") return <div key={el.id} className="cv-el cv-el--shape" style={style} />;
          return (
            <div key={el.id} className="cv-el cv-el--text" style={style}>
              <div className="cv-wrap">
                <div className="cv-text-inner">
                  <RichView doc={el.body} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
