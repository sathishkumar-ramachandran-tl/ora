import tailwindcssAnimate from "tailwindcss-animate";

const oraRgb = (name, fallback) => `rgb(var(${name}, ${fallback}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ora: {
          canvas: oraRgb("--ora-canvas", "246 247 245"),
          surface: oraRgb("--ora-surface", "255 255 255"),
          subtle: oraRgb("--ora-surface-subtle", "240 242 239"),
          "surface-subtle": oraRgb("--ora-surface-subtle", "240 242 239"),
          ink: oraRgb("--ora-text-primary", "24 32 29"),
          primary: oraRgb("--ora-text-primary", "24 32 29"),
          secondary: oraRgb("--ora-text-secondary", "98 106 102"),
          tertiary: oraRgb("--ora-text-tertiary", "146 153 149"),
          muted: oraRgb("--ora-text-secondary", "98 106 102"),
          border: oraRgb("--ora-border", "229 232 228"),
          "border-strong": oraRgb("--ora-border-strong", "213 217 212"),
          nav: oraRgb("--ora-nav", "23 32 30"),
          "nav-surface": oraRgb("--ora-nav-surface", "32 44 40"),
          "nav-muted": oraRgb("--ora-nav-muted", "164 176 169"),
          accent: oraRgb("--ora-accent", "35 103 232"),
          "accent-hover": oraRgb("--ora-accent-hover", "25 87 203"),
          "accent-strong": oraRgb("--ora-accent-strong", "21 72 168"),
          "accent-soft": oraRgb("--ora-accent-soft", "234 241 255"),
          success: oraRgb("--ora-success", "15 112 77"),
          "success-soft": oraRgb("--ora-success-soft", "231 247 239"),
          warning: oraRgb("--ora-warning", "138 86 15"),
          "warning-soft": oraRgb("--ora-warning-soft", "255 243 214"),
          danger: oraRgb("--ora-danger", "182 53 45"),
          "danger-soft": oraRgb("--ora-danger-soft", "252 232 230"),
          info: oraRgb("--ora-info", "49 95 143"),
          "info-soft": oraRgb("--ora-info-soft", "234 243 255"),
        },
        canvas: oraRgb("--ora-canvas", "246 247 245"),
        surface: oraRgb("--ora-surface", "255 255 255"),
        "surface-subtle": oraRgb("--ora-surface-subtle", "240 242 239"),
        foreground: oraRgb("--ora-text-primary", "24 32 29"),
        muted: oraRgb("--ora-text-secondary", "98 106 102"),
        secondary: oraRgb("--ora-text-secondary", "98 106 102"),
        tertiary: oraRgb("--ora-text-tertiary", "146 153 149"),
        "border-subtle": oraRgb("--ora-border", "229 232 228"),
        accent: oraRgb("--ora-accent", "35 103 232"),
        "accent-soft": oraRgb("--ora-accent-soft", "234 241 255"),
        neural: {
          slate: "#0f172a", // Deep Slate — base chrome
          indigo: "#2367E8", // Ora accent mirror for legacy consumers
          emerald: "#10b981", // Neural Emerald — success / live-status
        },
        brand: {
          DEFAULT: "#2367E8",
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
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(35, 103, 232, 0.12), 0 16px 40px 0 rgba(24, 32, 29, 0.08)",
        "glow-emerald": "0 0 0 1px rgba(16, 185, 129, 0.15), 0 0 24px 0 rgba(16, 185, 129, 0.35)",
        glass: "0 18px 48px 0 rgba(24, 32, 29, 0.12)",
        soft: "0 14px 40px rgba(24, 32, 29, 0.08)",
      },
      backdropBlur: {
        xs: "2px",
      },
      keyframes: {
        "glow-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
      animation: {
        "glow-pulse": "glow-pulse 2.5s ease-in-out infinite",
      },
    },
  },
  plugins: [
    tailwindcssAnimate,
  ],
}
