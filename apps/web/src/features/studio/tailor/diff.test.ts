import { describe, expect, it } from "vitest";
import { diffWords, pairLines } from "./diff";

const joined = (pieces: { text: string; kind: string }[], kind: string) =>
  pieces
    .filter((p) => p.kind === kind)
    .map((p) => p.text.trim())
    .join("|");

describe("word differences", () => {
  it("marks only the words that changed", () => {
    const d = diffWords("Built a dashboard for 6 teams", "Built a Tableau dashboard for 6 teams");
    expect(joined(d.after, "added")).toBe("Tableau");
    expect(joined(d.before, "removed")).toBe("");
  });

  it("marks removed and added words on their own sides", () => {
    const d = diffWords("Cut reporting from two days to two hours", "Cut reporting from two days to 2 hours");
    expect(joined(d.before, "removed")).toBe("two");
    expect(joined(d.after, "added")).toBe("2");
  });

  it("rebuilds both texts exactly from the pieces", () => {
    const before = "Led a team of five analysts";
    const after = "Led five analysts on a team";
    const d = diffWords(before, after);
    expect(d.before.map((p) => p.text).join("")).toBe(before);
    expect(d.after.map((p) => p.text).join("")).toBe(after);
  });

  it("says nothing changed for equal text", () => {
    const d = diffWords("same words", "same words");
    expect(d.before).toEqual([{ text: "same words", kind: "same" }]);
    expect(d.after).toEqual([{ text: "same words", kind: "same" }]);
  });
});

describe("pairing lines", () => {
  it("puts an added line beside nothing and a dropped line beside nothing", () => {
    const rows = pairLines(["one", "two"], ["one"]);
    expect(rows[1]!.after).toBeNull();
    expect(rows[1]!.before).toEqual([{ text: "two", kind: "removed" }]);
    const added = pairLines(["one"], ["one", "extra"]);
    expect(added[1]!.before).toBeNull();
    expect(added[1]!.after).toEqual([{ text: "extra", kind: "added" }]);
  });
});
