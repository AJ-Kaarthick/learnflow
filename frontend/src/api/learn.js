import { API_BASE_URL, apiFetch } from "./config.js";
import { parseErrorResponse } from "./errors.js";

/**
 * Requests a structured curriculum / study outline across 1 to 10 selected documents.
 * The backend enforces server-side document ownership, document readiness, and guest AI quotas.
 */
export async function generateLearnOutline({ documentIds, depth = "standard" }) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/study/learn/outline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, depth }),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate a curriculum right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Curriculum generation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Generates a RAG-grounded topic deep-dive explanation with source citations,
 * key terms, key takeaways, and optional contextual actions (simplify, elaborate, example).
 */
export async function generateLearnTopic({
  documentIds,
  topicId,
  topicTitle,
  action = null,
  depth = "standard",
  parentTopicTitle = null,
  context = null,
}) {
  const payload = {
    document_ids: documentIds,
    topic_id: topicId,
    topic_title: topicTitle,
    action: action || null,
    depth: depth || "standard",
  };

  if (parentTopicTitle) {
    payload.parent_topic_title = parentTopicTitle;
  }
  if (context) {
    payload.context = context;
  }

  const response = await apiFetch(`${API_BASE_URL}/api/v1/study/learn/topic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate this topic explanation right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Topic generation failed (status ${response.status})`);
  }

  return response.json();
}
