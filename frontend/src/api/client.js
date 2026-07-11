// Vite only exposes env vars prefixed with VITE_ to the browser (this is
// a security boundary — it stops you from accidentally shipping a secret
// key to every visitor's browser). We read the backend URL from one, with
// a sensible local-dev fallback so the app still works with zero setup.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Checks whether the backend is reachable and healthy.
 * Every other API call we add in later milestones (upload, summary,
 * flashcards...) will follow this same shape: a small function here
 * that components call, instead of components calling fetch() directly.
 * That keeps the URL, error handling, and JSON parsing in one place.
 */
export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`Backend responded with status ${response.status}`);
  }

  return response.json();
}
