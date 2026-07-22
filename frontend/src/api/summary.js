import { API_BASE_URL } from "./config";

/**
 * Requests a summary for a document. The backend returns a cached
 * summary if one already exists, or generates a new one — either way
 * this call is safe to make more than once.
 */
export async function generateSummary(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/summary`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate a summary right now. Please try again in a moment.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Summary generation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Loads an existing summary without generating one. Returns null if
 * none exists yet — that's the normal, expected state for a document
 * that hasn't been summarized, not an error.
 */
export async function getSummary(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/summary`);

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Could not load summary (status ${response.status})`);
  }

  return response.json();
}
