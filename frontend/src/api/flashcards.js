import { API_BASE_URL } from "./config";

/**
 * Requests flashcards for a document. Returns cached cards if they
 * already exist, or generates a new set — safe to call more than once.
 */
export async function generateFlashcards(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/flashcards`, {
    method: "POST",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Flashcard generation failed (status ${response.status})`
    );
  }

  return response.json();
}
