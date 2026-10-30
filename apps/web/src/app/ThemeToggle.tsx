import { THEME_CHOICES, useTheme } from "../lib/theme";
import type { ThemeChoice } from "../lib/theme";
import { SegmentedControl } from "../ui";

const LABELS: Record<ThemeChoice, string> = { system: "System", light: "Light", dark: "Dark" };
const OPTIONS = THEME_CHOICES.map((value) => ({ value, label: LABELS[value] }));

/** Appearance choice. "System" follows the operating system and is the default. */
export function ThemeToggle() {
  const [choice, setChoice] = useTheme();
  return <SegmentedControl legend="Theme" options={OPTIONS} value={choice} onChange={setChoice} />;
}
