import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite is the dev server + build tool. It compiles JSX, serves the app
// with hot-reload while we work, and bundles everything for production.
// The two plugins below teach it to understand React syntax and to
// process Tailwind's utility classes.
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
