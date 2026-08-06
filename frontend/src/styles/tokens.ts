/**
 * Raw design-token values for consumers that can't use Tailwind classes
 * (D3 in KnowledgeGraph.tsx, canvas rendering in SpatialCanvas.tsx).
 * Keep in sync with the `neural`/`brand` scales in tailwind.config.js —
 * this file is the non-Tailwind mirror of that palette, not a second source of truth.
 */

export const neural = {
  slate: "#0f172a",
  indigo: "#4f46e5",
  emerald: "#10b981",
} as const;

export const brand = {
  50: "#eef2ff",
  100: "#e0e7ff",
  200: "#c7d2fe",
  300: "#a5b4fc",
  400: "#818cf8",
  500: "#6366f1",
  600: "#4f46e5",
  700: "#4338ca",
  800: "#3730a3",
  900: "#312e81",
} as const;

export const status = {
  success: neural.emerald,
  danger: "#f43f5e", // rose-500
  warning: "#f59e0b", // amber-500
  info: brand[500],
} as const;

export const fontFamily = "Inter, ui-sans-serif, system-ui, sans-serif";
