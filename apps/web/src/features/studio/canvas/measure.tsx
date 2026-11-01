import { renderToStaticMarkup } from "react-dom/server";
import { elementCss, reactStyle } from "./css";
import type { Measure } from "./convert";
import { RichView } from "./rich";

/**
 * Ask the browser how tall a text element is at its width. It draws the same markup with the same
 * CSS in a hidden box and reads the height back, in millimetres. Needs real layout, so it is used
 * in the browser and replaced by a stand-in in unit tests.
 */
export function browserMeasure(): { measure: Measure; dispose: () => void } {
  const host = document.createElement("div");
  host.className = "cv-text cv-measure";
  host.setAttribute("aria-hidden", "true");
  Object.assign(host.style, { position: "absolute", left: "-10000px", top: "0", visibility: "hidden" });
  document.body.appendChild(host);
  const measure: Measure = (el, style) => {
    const css = elementCss(el, style, 1);
    const { position: _p, left: _l, top: _t, zIndex: _z, minHeight: _m, ...rest } = reactStyle(css) as Record<string, string>;
    host.removeAttribute("style");
    Object.assign(host.style, { position: "absolute", left: "-10000px", top: "0", visibility: "hidden", ...rest });
    host.innerHTML = el.body && el.body.content.length > 0 ? renderToStaticMarkup(<RichView doc={el.body} />) : "<p>&nbsp;</p>";
    return (host.getBoundingClientRect().height * 25.4) / 96;
  };
  return { measure, dispose: () => host.remove() };
}
