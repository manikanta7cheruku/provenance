/** A word by word difference between two pieces of text, for showing what a suggestion changes. */

export interface Piece {
  text: string;
  kind: "same" | "added" | "removed";
}

const tokens = (text: string) => text.split(/(\s+)/).filter((t) => t !== "");

/** Longest common subsequence of words, so only real changes are marked. */
export function diffWords(before: string, after: string): { before: Piece[]; after: Piece[] } {
  const a = tokens(before);
  const b = tokens(after);
  const table: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i]![j] = a[i] === b[j] ? table[i + 1]![j + 1]! + 1 : Math.max(table[i + 1]![j]!, table[i]![j + 1]!);
    }
  }
  const left: Piece[] = [];
  const right: Piece[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      left.push({ text: a[i]!, kind: "same" });
      right.push({ text: b[j]!, kind: "same" });
      i += 1;
      j += 1;
    } else if (table[i + 1]![j]! >= table[i]![j + 1]!) {
      left.push({ text: a[i]!, kind: "removed" });
      i += 1;
    } else {
      right.push({ text: b[j]!, kind: "added" });
      j += 1;
    }
  }
  for (; i < a.length; i += 1) left.push({ text: a[i]!, kind: "removed" });
  for (; j < b.length; j += 1) right.push({ text: b[j]!, kind: "added" });
  return { before: merge(left), after: merge(right) };
}

function merge(pieces: Piece[]): Piece[] {
  const out: Piece[] = [];
  for (const piece of pieces) {
    const last = out[out.length - 1];
    if (last && last.kind === piece.kind) last.text += piece.text;
    else out.push({ ...piece });
  }
  return out;
}

/** Pair the lines of a before and after list for display. A line that was added or dropped sits beside nothing. */
export function pairLines(before: string[], after: string[]): { before: Piece[] | null; after: Piece[] | null }[] {
  const rows = Math.max(before.length, after.length);
  return Array.from({ length: rows }, (_, i) => {
    const b = before[i];
    const a = after[i];
    if (b !== undefined && a !== undefined) return diffWords(b, a);
    if (b !== undefined) return { before: [{ text: b, kind: "removed" as const }], after: null };
    return { before: null, after: [{ text: a!, kind: "added" as const }] };
  });
}
