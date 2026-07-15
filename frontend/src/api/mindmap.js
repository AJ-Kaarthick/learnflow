import { API_BASE_URL } from "./config";

export async function generateMindMap(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/mindmap`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error(
        "The AI couldn't generate a mind map right now. Please try again in a moment."
      );
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Mind map generation failed (status ${response.status})`
    );
  }

  return response.json();
}
