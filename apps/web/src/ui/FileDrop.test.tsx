import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { checkFile, FileDrop, formatBytes } from "./FileDrop";

const EXTENSIONS = [".pdf", ".docx"];
const LIMIT = 5 * 1024 * 1024;

function file(name: string, bytes: number): File {
  return new File([new Uint8Array(bytes)], name);
}

describe("formatBytes", () => {
  it("uses B, KB and MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("checkFile", () => {
  it("accepts a supported file within the limit, in any letter case", () => {
    expect(checkFile(file("cv.pdf", 100), EXTENSIONS, LIMIT)).toBeNull();
    expect(checkFile(file("CV.DOCX", 100), EXTENSIONS, LIMIT)).toBeNull();
  });
  it("rejects an unsupported type with a sentence that says what to do", () => {
    expect(checkFile(file("photo.png", 100), EXTENSIONS, LIMIT)).toBe(
      "This file type is not supported. Choose a .pdf or .docx file.",
    );
  });
  it("rejects an empty file", () => {
    expect(checkFile(file("cv.pdf", 0), EXTENSIONS, LIMIT)).toContain("empty");
  });
  it("rejects a file over the limit and names both sizes", () => {
    const message = checkFile(file("cv.pdf", LIMIT + 1), EXTENSIONS, LIMIT);
    expect(message).toContain("over the 5.0 MB limit");
  });
});

describe("FileDrop", () => {
  function setup(overrides: Partial<ComponentProps<typeof FileDrop>> = {}) {
    const onSelect = vi.fn();
    const onReject = vi.fn();
    render(
      <FileDrop
        label="Resume"
        hint="PDF or DOCX, up to 5 MB."
        extensions={EXTENSIONS}
        maxBytes={LIMIT}
        file={null}
        onSelect={onSelect}
        onReject={onReject}
        {...overrides}
      />,
    );
    return { onSelect, onReject };
  }

  it("passes a valid file to onSelect", async () => {
    const { onSelect, onReject } = setup();
    await userEvent.upload(screen.getByLabelText("Resume"), file("cv.pdf", 1024));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onReject).not.toHaveBeenCalled();
  });

  it("passes a rejected file to onReject and never to onSelect", async () => {
    const { onSelect, onReject } = setup();
    await userEvent.upload(screen.getByLabelText("Resume"), file("notes.txt", 10), { applyAccept: false });
    expect(onReject).toHaveBeenCalledOnce();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("links the hint and the error to the input and marks it invalid", () => {
    setup({ error: "Choose a smaller file." });
    const input = screen.getByLabelText("Resume");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect((input.getAttribute("aria-describedby") ?? "").split(" ")).toHaveLength(2);
    expect(screen.getByRole("alert").textContent).toBe("Choose a smaller file.");
  });

  it("shows the chosen file by name and size", () => {
    setup({ file: { name: "cv.pdf", size: 2048 } });
    expect(screen.getByText("cv.pdf")).toBeTruthy();
    expect(screen.getByText("(2 KB)")).toBeTruthy();
  });
});
