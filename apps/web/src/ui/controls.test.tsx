import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Checkbox, Select, TextArea } from "./Fields";
import { SegmentedControl } from "./SegmentedControl";
import { Skeleton } from "./Skeleton";

const OPTIONS = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
  { value: "c", label: "Gamma" },
] as const;

function Harness() {
  const [value, setValue] = useState<"a" | "b" | "c">("a");
  return <SegmentedControl legend="Pick one" options={OPTIONS} value={value} onChange={setValue} />;
}

function checked(name: string): boolean {
  return (screen.getByRole("radio", { name }) as HTMLInputElement).checked;
}

describe("SegmentedControl", () => {
  it("is a named group of radios with the current value checked", () => {
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Pick one" })).toBeTruthy();
    expect(checked("Alpha")).toBe(true);
    expect(checked("Beta")).toBe(false);
  });

  it("changes on click", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("radio", { name: "Gamma" }));
    expect(checked("Gamma")).toBe(true);
  });

  it("moves with the arrow keys using the native radio behavior", async () => {
    render(<Harness />);
    screen.getByRole("radio", { name: "Alpha" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(checked("Beta")).toBe(true);
  });
});

describe("field wiring", () => {
  it("links hint and error to a multiline field and marks it invalid", () => {
    render(<TextArea label="Notes" hint="Keep it short." error="Add at least one sentence." />);
    const field = screen.getByLabelText("Notes");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    expect((field.getAttribute("aria-describedby") ?? "").split(" ")).toHaveLength(2);
  });

  it("does not mark a field invalid without an error", () => {
    render(
      <Select label="Fit">
        <option>One</option>
      </Select>,
    );
    expect(screen.getByLabelText("Fit").hasAttribute("aria-invalid")).toBe(false);
  });

  it("links a checkbox error to the checkbox", () => {
    render(<Checkbox label="I agree" error="You must agree to continue." />);
    const box = screen.getByRole("checkbox", { name: "I agree" });
    expect(box.getAttribute("aria-invalid")).toBe("true");
    expect(box.getAttribute("aria-describedby")).toBeTruthy();
  });
});

describe("Skeleton", () => {
  it("announces what is loading and hides the shapes", () => {
    const { container } = render(<Skeleton label="Loading your jobs" lines={4} />);
    expect(screen.getByRole("status").textContent).toBe("Loading your jobs");
    expect(container.querySelectorAll(".skeleton__line")).toHaveLength(4);
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });
});
