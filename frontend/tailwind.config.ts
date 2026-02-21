import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      keyframes: {
        blob: {
          "0%": { transform: "translate(0px, 0px) scale(1)" },
          "33%": { transform: "translate(30px, -40px) scale(1.05)" },
          "66%": { transform: "translate(-20px, 35px) scale(0.98)" },
          "100%": { transform: "translate(0px, 0px) scale(1)" },
        },
        grainShift: {
          "0%": { transform: "translate3d(0, 0, 0)" },
          "100%": { transform: "translate3d(-40px, 25px, 0)" },
        },
      },
      animation: {
        blob: "blob 12s ease-in-out infinite",
        grain: "grainShift 8s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;