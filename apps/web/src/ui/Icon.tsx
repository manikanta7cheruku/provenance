/**
 * The product's icon set: simple outline shapes on a 24 by 24 grid, drawn here so nothing is fetched
 * and every icon takes its color from the text around it. Icons are decoration next to a word, so they
 * are hidden from assistive technology. An icon that stands alone must be given a label by its button.
 */
const PATHS = {
  briefcase: ["M4 7.5h16a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1Z", "M9 7.5V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v1.5", "M3 13h18"],
  search: ["M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z", "m20 20-4-4"],
  bookmark: ["M6.5 3.5h11a1 1 0 0 1 1 1V21l-6.5-4.2L5.5 21V4.5a1 1 0 0 1 1-1Z"],
  send: ["M21 3 10.5 13.5", "M21 3l-6.5 18-4-7.5L3 9.5 21 3Z"],
  user: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4 20.5c.8-3.6 4-5.5 8-5.5s7.2 1.9 8 5.5"],
  document: ["M7 3.5h7l5 5V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 7 20V3.5Z", "M14 3.5v5h5", "M10 13h6", "M10 16.5h6"],
  activity: ["M3 12h4l3-8 4 16 3-8h4"],
  sliders: ["M4 6h9", "M17 6h3", "M4 12h3", "M11 12h9", "M4 18h11", "M19 18h1", "M15 6m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0", "M9 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0", "M17 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0"],
  shield: ["M12 3 20 6v6c0 4.6-3.2 7.8-8 9-4.8-1.2-8-4.4-8-9V6l8-3Z", "m9 12 2 2 4-4"],
  inbox: ["M3 13.5 6 5.5h12l3 8", "M3 13.5V19a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-5.5h-5.5l-1 2.5h-5l-1-2.5H3Z"],
  check: ["M5 12.5 10 17.5 19 7"],
  alert: ["M12 4 3 19.5h18L12 4Z", "M12 10v4.5", "M12 17.2v.1"],
  info: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "M12 11v5", "M12 7.8v.1"],
  sun: ["M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M12 2.5v2", "M12 19.5v2", "M2.5 12h2", "M19.5 12h2", "m5.2 5.2 1.4 1.4", "m17.4 17.4 1.4 1.4", "m5.2 18.8 1.4-1.4", "m17.4 6.6 1.4-1.4"],
  moon: ["M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"],
  monitor: ["M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z", "M9 21h6", "M12 17v4"],
  plus: ["M12 5v14", "M5 12h14"],
  eye: ["M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z", "M12 14.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6Z"],
  eyeOff: ["M4 4l16 16", "M9.9 5.8A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-3 3.8", "M6.2 7.9A15.8 15.8 0 0 0 2.5 12S6 18.5 12 18.5a9.5 9.5 0 0 0 4-.9", "M10.2 10.3a2.8 2.8 0 0 0 3.5 3.5"],
  panel: ["M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z", "M9 5v14"],
  x: ["M6 6l12 12", "M18 6 6 18"],
  more: ["M5 12h.01", "M12 12h.01", "M19 12h.01"],
  arrow: ["M5 12h14", "m13 6 6 6-6 6"],
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
