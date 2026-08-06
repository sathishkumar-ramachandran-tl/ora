import tailwindcssAnimate from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      // "Neural" brand palette — sourced from frontend/WEBSITE_DESIGN.md,
      // shared with frontend/src/styles/tokens.ts for non-Tailwind consumers (D3, canvas).
      colors: {
        neural: {
          slate: "#0f172a", // Deep Slate — base chrome
          indigo: "#4f46e5", // Electric Indigo — primary accent
          emerald: "#10b981", // Neural Emerald — success / live-status
        },
        brand: {
          DEFAULT: "#4f46e5",
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
        glow: "0 0 0 1px rgba(79, 70, 229, 0.15), 0 0 24px 0 rgba(79, 70, 229, 0.35)",
        "glow-emerald": "0 0 0 1px rgba(16, 185, 129, 0.15), 0 0 24px 0 rgba(16, 185, 129, 0.35)",
        glass: "0 8px 32px 0 rgba(15, 23, 42, 0.37)",
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
