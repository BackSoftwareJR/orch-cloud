/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "SF Mono",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "#0a0a0f",
          raised: "#12121a",
          glass: "rgba(18, 18, 26, 0.72)",
        },
        accent: {
          DEFAULT: "#6366f1",
          glow: "#818cf8",
        },
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0, 0, 0, 0.37)",
        glow: "0 0 40px rgba(99, 102, 241, 0.15)",
      },
      backdropBlur: {
        glass: "20px",
      },
    },
  },
  plugins: [],
};
