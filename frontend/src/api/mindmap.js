import { API_BASE_URL, apiFetch } from "./config";
import { parseErrorResponse } from "./errors.js";

export async function generateMindMap(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/mindmap`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error(
        "The AI couldn't generate a mind map right now. Please try again in a moment."
      );
    }
    throw await parseErrorResponse(response, `Mind map generation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Loads an existing mind map without generating one. Returns null if
 * none exists yet.
 */
export async function getMindMap(documentId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/mindmap`);

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load mind map (status ${response.status})`);
  }

  return response.json();
}
