/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { navy: "#1f3a5f", brand: "#2e5a88" },
    },
  },
  plugins: [],
};
