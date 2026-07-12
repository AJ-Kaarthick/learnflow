import { API_BASE_URL } from "./config";

export async function generateQuiz(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/quiz`, {
    method: "POST",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Quiz generation failed (status ${response.status})`);
  }

  return response.json();
}
