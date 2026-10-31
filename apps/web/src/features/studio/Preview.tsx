import { useEffect, useRef, useState } from "react";

const PAPER_PX: Record<string, { width: number; height: number }> = {
  a4: { width: 794, height: 1123 },
  letter: { width: 816, height: 1056 },
};

interface PreviewProps {
  html: string | null;
  paper: string;
  failed: boolean;
}

/**
 * The resume as the server renders it. The frame has no scripts: the page is built from validated
 * data. `allow-same-origin` only lets this screen read the frame's height. The page is scaled to
 * fit the column, and a line says how many pages it is about, because the PDF is the exact one.
 */
export function Preview({ html, paper, failed }: PreviewProps) {
  const box = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const [scale, setScale] = useState(1);
  const [height, setHeight] = useState(PAPER_PX.a4?.height ?? 1123);
  const size = PAPER_PX[paper] ?? { width: 794, height: 1123 };

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const update = () => setScale(Math.min(1, element.clientWidth / size.width) || 1);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [size.width]);

  function measure() {
    const doc = frame.current?.contentDocument;
    if (doc) setHeight(Math.max(size.height, doc.documentElement.scrollHeight));
  }

  const pages = Math.max(1, Math.ceil((height - 32) / size.height));
  return (
    <div className="preview">
      <p className="preview__note" role="status">
        {html === null
          ? "Preparing the preview"
          : `Preview, about ${pages} ${pages === 1 ? "page" : "pages"}. The PDF is the exact version.`}
        {failed ? " The preview could not update. Showing the last one." : ""}
      </p>
      <div ref={box} className="preview__box" style={{ height: height * scale }}>
        {html !== null ? (
          <iframe
            ref={frame}
            title="Resume preview"
            sandbox="allow-same-origin"
            srcDoc={html}
            onLoad={measure}
            className="preview__frame"
            style={{
              width: size.width,
              height,
              transform: `scale(${scale})`,
              transformOrigin: "top left",
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
