// Vite only exposes env vars prefixed with VITE_ to the browser (a
// security boundary — it stops a real secret from accidentally
// shipping to every visitor). We read the backend URL from one, with
// a local-dev fallback so the app works with zero setup.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
