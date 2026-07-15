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
