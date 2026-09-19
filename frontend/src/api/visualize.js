import { API_BASE_URL, apiFetch } from "./config.js";
import { parseErrorResponse } from "./errors.js";

/**
 * Requests an interactive concept network graph across 1 to 10 selected documents.
 * The backend enforces server-side document ownership, document readiness,
 * guest AI quotas, bounded node/edge counts, and grounded source citations.
 */
export async function generateVisualizeGraph({ documentIds, depth = "standard" }) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/study/visualize/graph`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, depth }),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate a concept visualization right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Concept visualization failed (status ${response.status})`);
  }

  return response.json();
}
