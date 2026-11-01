import { act, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/api";
import type { ResumeContent, ResumeDocument, StudioOptions } from "../../lib/studio-api";
import { ACCENT_PRESETS, accentProblem, contrastOnWhite, isHexColor } from "./contrast";
import { ContentEditor } from "./ContentEditor";
import {
  addBlock,
  addSection,
  moveBlock,
  moveSection,
  removeBlock,
  removeSection,
  sameDocument,
  setStyle,
  updateBlock,
} from "./doc-ops";
import { StylePanel } from "./StylePanel";
import { useStudioDocument } from "./useStudioDocument";

const api = vi.hoisted(() => ({
  saveResume: vi.fn(),
  previewResume: vi.fn(),
}));
vi.mock("../../lib/studio-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/studio-api")>()),
  ...api,
}));

function content(overrides: Partial<ResumeContent> = {}): ResumeContent {
  return {
    version: 1,
    style: {
      template: "classic",
      font_pair: "plex-newsreader",
      size: "medium",
      spacing: "normal",
      margins: "normal",
      accent: "#222222",
      divider: "thin",
      paper: "a4",
    },
    header: { name: "Asha Rao", headline: "", contacts: ["asha@example.com"] },
    sections: [
      {
        id: "s1",
        kind: "experience",
        title: "Experience",
        blocks: [
          { id: "b1", heading: "Data Intern", subheading: "Kestrel", dates: "2025", location: "", body: null },
          { id: "b2", heading: "Backend Intern", subheading: "Lumen", dates: "2024", location: "", body: null },
        ],
      },
      { id: "s2", kind: "education", title: "Education", blocks: [] },
    ],
    ...overrides,
  };
}

const OPTIONS: StudioOptions = {
  templates: [
    { key: "classic", name: "Classic", description: "Traditional", ats_safe: true },
    { key: "modern", name: "Modern", description: "Accent color", ats_safe: true },
  ],
  font_pairs: [{ key: "plex-newsreader", label: "Serif headings, sans body" }],
  sizes: ["small", "medium", "large"],
  spacings: ["tight", "normal", "relaxed"],
  margins: ["narrow", "normal", "wide"],
  dividers: ["none", "thin", "bold", "dotted"],
  papers: ["a4", "letter"],
  section_kinds: ["summary", "experience", "custom"],
  max_resumes: 1,
};

describe("document edits", () => {
  it("never change the document they were given", () => {
    const doc = content();
    const before = JSON.stringify(doc);
    addSection(doc, "skills");
    moveSection(doc, 0, 1);
    removeSection(doc, 0);
    addBlock(doc, 0);
    moveBlock(doc, 0, 0, 1);
    removeBlock(doc, 0, 0);
    updateBlock(doc, 0, 0, { heading: "x" });
    setStyle(doc, { size: "large" });
    expect(JSON.stringify(doc)).toBe(before);
  });

  it("add a section at the end with a title and one empty item", () => {
    const next = addSection(content(), "skills");
    expect(next.sections.at(-1)?.title).toBe("Skills");
    expect(next.sections.at(-1)?.blocks).toHaveLength(1);
  });

  it("move items and sections by one place and stop at the ends", () => {
    const doc = content();
    expect(moveSection(doc, 0, 1).sections.map((s) => s.id)).toEqual(["s2", "s1"]);
    expect(moveSection(doc, 0, -1)).toEqual(doc);
    expect(moveBlock(doc, 0, 1, -1).sections[0]?.blocks.map((b) => b.id)).toEqual(["b2", "b1"]);
    expect(moveBlock(doc, 0, 1, 1)).toEqual(doc);
  });

  it("remove, update and compare", () => {
    const doc = content();
    expect(removeBlock(doc, 0, 0).sections[0]?.blocks.map((b) => b.id)).toEqual(["b2"]);
    expect(updateBlock(doc, 0, 1, { dates: "2023" }).sections[0]?.blocks[1]?.dates).toBe("2023");
    expect(sameDocument(doc, content())).toBe(true);
    expect(sameDocument(doc, setStyle(doc, { size: "large" }))).toBe(false);
  });
});

describe("accent colors", () => {
  it("knows black from white and rejects what is too light to read", () => {
    expect(contrastOnWhite("#000000")).toBeCloseTo(21, 0);
    expect(accentProblem("#ffee88")).toMatch(/too light/);
    expect(accentProblem("red")).toMatch(/hex|like #/i);
    expect(accentProblem("#1f3d7a")).toBeNull();
    expect(isHexColor("#12345")).toBe(false);
  });
  it("offers only presets that pass", () => {
    for (const preset of ACCENT_PRESETS) expect(accentProblem(preset.value)).toBeNull();
  });
});

describe("the content editor", () => {
  function Harness({ announce = vi.fn() }: { announce?: (m: string) => void }) {
    const [doc, setDoc] = useState(content());
    return (
      <>
        <ContentEditor doc={doc} onChange={setDoc} problems={{}} epoch={0} announce={announce} />
        <output data-testid="json">{JSON.stringify(doc)}</output>
      </>
    );
  }

  it("changes the name as you type", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const name = screen.getByLabelText("Full name");
    await user.clear(name);
    await user.type(name, "Meera Nair");
    expect(screen.getByTestId("json").textContent).toContain('"name":"Meera Nair"');
  });

  it("labels the fields for the kind of section", () => {
    render(<Harness />);
    expect(screen.getAllByLabelText("Role").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("Company").length).toBeGreaterThan(0);
    expect(screen.queryAllByLabelText("Degree or course")).toHaveLength(0);
  });

  it("moves a section and says so for screen readers", async () => {
    const announce = vi.fn();
    const user = userEvent.setup();
    render(<Harness announce={announce} />);
    await user.click(screen.getByRole("button", { name: "Move down, Experience" }));
    expect(announce).toHaveBeenCalledWith("Experience moved down to position 2.");
    expect(JSON.parse(screen.getByTestId("json").textContent ?? "{}").sections[0].id).toBe("s2");
  });

  it("disables moves at the ends", () => {
    render(<Harness />);
    expect((screen.getByRole("button", { name: "Move up, Experience" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("asks before removing a section", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Remove section, Education" }));
    expect(JSON.parse(screen.getByTestId("json").textContent ?? "{}").sections).toHaveLength(2);
    await user.click(await screen.findByRole("button", { name: /^Remove section$/ }));
    await waitFor(() => expect(JSON.parse(screen.getByTestId("json").textContent ?? "{}").sections).toHaveLength(1));
  });

  it("adds a section and an item", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Add section" }));
    expect(JSON.parse(screen.getByTestId("json").textContent ?? "{}").sections).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Add an item to Education" }));
    expect(JSON.parse(screen.getByTestId("json").textContent ?? "{}").sections[1].blocks).toHaveLength(1);
  });

  it("shows a server message next to its field", () => {
    render(
      <ContentEditor
        doc={content()}
        onChange={() => undefined}
        problems={{ "header.name": "This is too long. Keep it under 120 characters." }}
        epoch={0}
        announce={() => undefined}
      />,
    );
    expect(screen.getByText("This is too long. Keep it under 120 characters.")).toBeTruthy();
    expect(screen.getByLabelText("Full name").getAttribute("aria-invalid")).toBe("true");
  });
});

describe("the design panel", () => {
  it("switches the template", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<StylePanel doc={content()} options={OPTIONS} onChange={onChange} problems={{}} />);
    await user.click(screen.getByRole("radio", { name: /Modern/ }));
    expect(onChange.mock.calls[0]?.[0].style.template).toBe("modern");
  });

  it("says plainly whether a template reads well in applicant tracking systems", () => {
    render(<StylePanel doc={content()} options={OPTIONS} onChange={() => undefined} problems={{}} />);
    expect(screen.getAllByText("Reads well in applicant tracking systems")).toHaveLength(2);
  });

  it("does not accept an accent that is too light, and explains why", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<StylePanel doc={content()} options={OPTIONS} onChange={onChange} problems={{}} />);
    const field = screen.getByLabelText("Custom color");
    await user.clear(field);
    await user.type(field, "#ffee88");
    expect(screen.getByText(/too light to read on white paper/)).toBeTruthy();
    expect(onChange).not.toHaveBeenCalled();
    await user.clear(field);
    await user.type(field, "#7a1f3d");
    expect(onChange.mock.calls.at(-1)?.[0].style.accent).toBe("#7a1f3d");
  });

  it("applies a preset color", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<StylePanel doc={content()} options={OPTIONS} onChange={onChange} problems={{}} />);
    await user.click(screen.getByRole("button", { name: "Navy" }));
    expect(onChange.mock.calls[0]?.[0].style.accent).toBe("#1f3d7a");
  });
});

describe("autosave", () => {
  const initial = {
    id: "r1",
    title: "My resume",
    revision: 3,
    template: "classic",
    updated_at: "2026-10-31T10:00:00Z",
    content: content(),
  };

  beforeEach(() => {
    vi.useFakeTimers();
    api.saveResume.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("saves after a pause, from the revision it started at, and then says saved", async () => {
    api.saveResume.mockResolvedValue({ id: "r1", revision: 4 });
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "large" })));
    expect(result.current.state).toBe("unsaved");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    expect(api.saveResume).toHaveBeenCalledTimes(1);
    expect(api.saveResume.mock.calls[0]?.[1].revision).toBe(3);
    expect(result.current.state).toBe("saved");
    expect(result.current.revision).toBe(4);
  });

  it("waits while the person keeps typing and saves once", async () => {
    api.saveResume.mockResolvedValue({ id: "r1", revision: 4 });
    const { result } = renderHook(() => useStudioDocument(initial));
    for (const size of ["small", "large", "medium", "large"]) {
      act(() => result.current.setContent(setStyle(result.current.content, { size })));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });
    }
    expect(api.saveResume).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    expect(api.saveResume).toHaveBeenCalledTimes(1);
    expect(api.saveResume.mock.calls[0]?.[1].content.style.size).toBe("large");
  });

  it("does not save when nothing changed", async () => {
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "medium" })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(api.saveResume).not.toHaveBeenCalled();
    expect(result.current.state).toBe("saved");
  });

  it("reports a conflict and keeps the person's edits on screen", async () => {
    api.saveResume.mockRejectedValue(new ApiError(409, "REVISION_CONFLICT", "changed elsewhere"));
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "large" })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    expect(result.current.state).toBe("conflict");
    expect(result.current.content.style.size).toBe("large");
  });

  it("keeps the server's messages for fields when the content is refused", async () => {
    api.saveResume.mockRejectedValue(
      new ApiError(422, "VALIDATION_FAILED", "Some details need fixing.", { "header.name": "Too long." }),
    );
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "large" })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    expect(result.current.state).toBe("error");
    expect(result.current.problems).toEqual({ "header.name": "Too long." });
  });

  it("saves again when edits arrive during a save", async () => {
    let finish: (value: unknown) => void = () => undefined;
    api.saveResume
      .mockImplementationOnce(() => new Promise((resolve) => (finish = resolve)))
      .mockResolvedValueOnce({ id: "r1", revision: 5 });
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "large" })));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    act(() => result.current.setContent(setStyle(result.current.content, { size: "small" })));
    await act(async () => {
      finish({ id: "r1", revision: 4 });
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(api.saveResume).toHaveBeenCalledTimes(2);
    expect(api.saveResume.mock.calls[1]?.[1].revision).toBe(4);
    expect(api.saveResume.mock.calls[1]?.[1].content.style.size).toBe("small");
    expect(result.current.state).toBe("saved");
  });

  it("flush saves right now", async () => {
    api.saveResume.mockResolvedValue({ id: "r1", revision: 4 });
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() => result.current.setContent(setStyle(result.current.content, { size: "large" })));
    await act(async () => {
      await result.current.flush();
    });
    expect(api.saveResume).toHaveBeenCalledTimes(1);
    expect(result.current.getRevision()).toBe(4);
  });

  it("replace swaps in a document from the server", () => {
    const { result } = renderHook(() => useStudioDocument(initial));
    act(() =>
      result.current.replace({ ...initial, revision: 9, content: setStyle(initial.content, { size: "small" }) }),
    );
    expect(result.current.revision).toBe(9);
    expect(result.current.content.style.size).toBe("small");
    expect(result.current.state).toBe("saved");
  });
});

describe("routing smoke", () => {
  it("renders the content editor inside a router without error", () => {
    const view = render(
      <MemoryRouter>
        <ContentEditor doc={content()} onChange={() => undefined} problems={{}} epoch={0} announce={() => undefined} />
      </MemoryRouter>,
    );
    expect(within(view.container).getByText("Your details")).toBeTruthy();
  });
});
