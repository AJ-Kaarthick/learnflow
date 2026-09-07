import { API_BASE_URL, apiFetch } from "./config";
import { parseErrorResponse } from "./errors.js";

export async function generateQuiz(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/quiz`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate a quiz right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Quiz generation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Loads existing quiz questions without generating any. Returns an
 * empty array if none exist yet.
 */
export async function getQuiz(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/quiz`);

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load quiz (status ${response.status})`);
  }

  return response.json();
}
