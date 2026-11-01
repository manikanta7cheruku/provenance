import { ActionButton } from "../../../ui";
import type { Order } from "./edit";
import type { CanvasDoc } from "./types";

interface LayersPanelProps {
  doc: CanvasDoc;
  selection: string[];
  onSelect: (ids: string[]) => void;
  onOrder: (ids: string[], how: Order) => void;
  onLock: (id: string, locked: boolean) => void;
}

/**
 * Every element in stacking order, topmost first. It is also the way to reach an element that is
 * hidden behind another, and the keyboard and screen reader way to change what is in front.
 */
export function LayersPanel({ doc, selection, onSelect, onOrder, onLock }: LayersPanelProps) {
  return (
    <div className="cv-layers">
      {doc.pages.map((page, pi) => (
        <section key={page.id} aria-label={`Layers on page ${pi + 1}`}>
          <h3 className="cv-layers__page">Page {pi + 1}</h3>
          {page.elements.length === 0 ? <p className="field__hint">Nothing on this page yet.</p> : null}
          <ol className="cv-layers__list">
            {[...page.elements].reverse().map((el, index, all) => (
              <li key={el.id} className={selection.includes(el.id) ? "is-selected" : undefined}>
                <button type="button" className="cv-layers__name" aria-pressed={selection.includes(el.id)} onClick={() => onSelect([el.id])}>
                  <span className="cv-layers__kind">{el.kind === "text" ? "Text" : "Shape"}</span> {el.name}
                  {el.locked ? <span className="cv-layers__locked"> (locked)</span> : null}
                </button>
                <span className="cv-layers__tools">
                  <ActionButton aria-label={`Bring ${el.name} forward`} disabled={index === 0} onClick={() => onOrder([el.id], "forward")}>
                    Forward
                  </ActionButton>
                  <ActionButton aria-label={`Send ${el.name} backward`} disabled={index === all.length - 1} onClick={() => onOrder([el.id], "backward")}>
                    Backward
                  </ActionButton>
                  <ActionButton aria-label={`${el.locked ? "Allow edits" : "Lock"} ${el.name}`} onClick={() => onLock(el.id, !el.locked)}>
                    {el.locked ? "Allow edits" : "Lock"}
                  </ActionButton>
                </span>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
