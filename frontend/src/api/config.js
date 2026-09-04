// Vite only exposes env vars prefixed with VITE_ to the browser (a
// security boundary — it stops a real secret from accidentally
// shipping to every visitor). We read the backend URL from one, with
// a local-dev fallback so the app works with zero setup.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Thin wrapper around the global `fetch` that every api/*.js module
 * uses instead of calling `fetch` directly (V3 Milestone 1 Phase 1).
 *
 * The backend now resolves a guest identity for every request via an
 * httponly session cookie (see backend/app/api/deps.py) — the browser
 * only sends that cookie automatically on same-origin requests, and
 * the frontend (localhost:5173) and backend (localhost:8000, or
 * whatever VITE_API_BASE_URL points at) are different origins, so
 * every request needs `credentials: "include"` or the cookie the
 * backend just issued would simply never come back on the next call,
 * silently starting a brand new guest identity every time. The
 * backend's CORS config already allows this (`allow_credentials=True`
 * with an explicit, non-wildcard origin — see app/main.py), it just
 * needed the frontend side of the handshake, which is this.
 *
 * A single wrapper here, rather than adding `credentials: "include"`
 * to all ~25 individual `fetch(...)` call sites across this
 * directory, keeps that one cross-cutting concern in one place.
 * Every other option (method, headers, body, signal, ...) is passed
 * through unchanged.
 */
export function apiFetch(url, options) {
  return fetch(url, { ...options, credentials: "include" });
}
