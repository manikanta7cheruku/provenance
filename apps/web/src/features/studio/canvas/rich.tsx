import type { ReactNode } from "react";
import type { RichDoc, RichNode } from "../../../lib/studio-api";

/** Draw a rich body as React. Every string is a text child, so nothing here can inject markup. */

function inline(node: RichNode, key: number): ReactNode {
  if (node.type === "hardBreak") return <br key={key} />;
  let out: ReactNode = node.text ?? "";
  for (const mark of node.marks ?? []) {
    if (mark.type === "bold") out = <strong>{out}</strong>;
    else if (mark.type === "italic") out = <em>{out}</em>;
    else if (mark.type === "underline") out = <u>{out}</u>;
    else if (mark.type === "highlight") out = <mark>{out}</mark>;
  }
  return <span key={key}>{out}</span>;
}

function block(node: RichNode, key: number): ReactNode {
  if (node.type === "paragraph") {
    return <p key={key}>{(node.content ?? []).map(inline)}</p>;
  }
  const Tag = node.type === "orderedList" ? "ol" : "ul";
  return (
    <Tag key={key}>
      {(node.content ?? []).map((item, i) => (
        <li key={i}>{(item.content ?? []).map(block)}</li>
      ))}
    </Tag>
  );
}

export function RichView({ doc }: { doc: RichDoc | null }) {
  if (!doc) return null;
  return <>{doc.content.map(block)}</>;
}

export function richText(doc: RichDoc | null): string {
  const lines: string[] = [];
  const walk = (node: RichNode, prefix: string) => {
    if (node.type === "paragraph") {
      lines.push(prefix + (node.content ?? []).map((c) => (c.type === "hardBreak" ? "\n" : (c.text ?? ""))).join(""));
    } else {
      (node.content ?? []).forEach((item, i) => {
        const mark = node.type === "orderedList" ? `${i + 1}. ` : "- ";
        (item.content ?? []).forEach((child) => walk(child, mark));
      });
    }
  };
  (doc?.content ?? []).forEach((n) => walk(n, ""));
  return lines.join("\n");
}

export function plainRich(text: string): RichDoc | null {
  const lines = text.split("\n").filter((l) => l.trim() !== "");
  if (lines.length === 0) return null;
  return {
    type: "doc",
    content: lines.map((line) => ({ type: "paragraph", content: [{ type: "text", text: line }] })),
  };
}

export function inlineDoc(parts: { text: string; marks?: ("bold" | "italic")[] }[]): RichDoc {
  return {
    type: "doc",
    content: [
      {
        type: "paragraph",
        content: parts
          .filter((p) => p.text !== "")
          .map((p) => ({
            type: "text",
            text: p.text,
            ...(p.marks && p.marks.length ? { marks: p.marks.map((type) => ({ type })) } : {}),
          })),
      },
    ],
  };
}
