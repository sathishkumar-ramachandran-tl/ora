/**
 * Raw design-token values for consumers that can't use Tailwind classes
 * (D3 in KnowledgeGraph.tsx, canvas rendering in SpatialCanvas.tsx).
 * Keep in sync with the `neural`/`brand` scales in tailwind.config.js —
 * this file is the non-Tailwind mirror of that palette, not a second source of truth.
 */

export const neural = {
  slate: "#17201E",
  indigo: "#2367E8",
  emerald: "#10b981",
} as const;

export const surface = {
  canvas: "#F2F4F1",
  raised: "#FFFFFF",
  muted: "#E9EDE8",
  ink: "#18201D",
  primary: "#18201D",
  secondary: "#626A66",
  tertiary: "#929995",
  border: "#D7DDD8",
  borderStrong: "#C2CCC4",
} as const;

export const navigation = {
  base: "#17201E",
  surface: "#202C28",
  muted: "#A4B0A9",
} as const;

export const brand = {
  50: "#EAF1FF",
  100: "#D6E4FF",
  200: "#ADC9FF",
  300: "#7FA7FA",
  400: "#4D83F1",
  500: "#2367E8",
  600: "#1957CB",
  700: "#1548A8",
  800: "#143C86",
  900: "#14346D",
} as const;

export const status = {
  success: "#0F704D",
  successSoft: "#E7F7EF",
  danger: "#B6352D",
  dangerSoft: "#FCE8E6",
  warning: "#8A560F",
  warningSoft: "#FFF3D6",
  info: "#315F8F",
  infoSoft: "#EAF3FF",
} as const;

export const semanticTokens = {
  canvas: surface.canvas,
  surface: surface.raised,
  surfaceSubtle: surface.muted,
  textPrimary: surface.primary,
  textSecondary: surface.secondary,
  textTertiary: surface.tertiary,
  borderSubtle: surface.border,
  borderStrong: surface.borderStrong,
  nav: navigation.base,
  navSurface: navigation.surface,
  navMuted: navigation.muted,
  accent: brand[500],
  accentHover: brand[600],
  accentStrong: brand[700],
  accentSoft: brand[50],
  success: status.success,
  successSoft: status.successSoft,
  warning: status.warning,
  warningSoft: status.warningSoft,
  danger: status.danger,
  dangerSoft: status.dangerSoft,
  info: status.info,
  infoSoft: status.infoSoft,
} as const;

export const fontFamily = "Inter, ui-sans-serif, system-ui, sans-serif";
