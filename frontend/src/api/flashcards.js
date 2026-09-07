import { API_BASE_URL, apiFetch } from "./config";
import { parseErrorResponse } from "./errors.js";

/**
 * Requests flashcards for a document. Returns cached cards if they
 * already exist, or generates a new set — safe to call more than once.
 */
export async function generateFlashcards(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/flashcards`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error(
        "The AI couldn't generate flashcards right now. Please try again in a moment."
      );
    }
    throw await parseErrorResponse(response, `Flashcard generation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Loads existing flashcards without generating any. Returns an empty
 * array if none exist yet — the backend's collection endpoint never
 * 404s, it just returns nothing.
 */
export async function getFlashcards(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/flashcards`);

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load flashcards (status ${response.status})`);
  }

  return response.json();
}
