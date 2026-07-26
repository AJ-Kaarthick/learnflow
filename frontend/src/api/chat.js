import { API_BASE_URL } from "./config";

/**
 * Chunks and embeds a document so it can be chatted with. Safe to
 * call more than once — the backend treats an already-indexed
 * document as a cheap no-op rather than re-embedding it. ChatPanel
 * calls this once when a document is opened, before allowing the
 * first message to be sent.
 */
export async function indexDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/index`, {
    method: "POST",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Could not prepare this document for chat (status ${response.status})`);
  }

  return response.json();
}

/**
 * Asks a grounded question about a document and returns the answer
 * plus the source chunks it was grounded in. The document must
 * already be indexed (see indexDocument above) — the backend returns
 * a 400 if it isn't.
 *
 * `history` is a plain array of { role: "user" | "assistant", content }
 * turns already in the conversation — ChatPanel holds this in React
 * state and resends it with every message so the model can resolve
 * follow-ups ("explain that more simply") without repeating the
 * original topic. Nothing is persisted server-side; the backend only
 * uses the most recent few turns of whatever's sent (see
 * MAX_HISTORY_TURNS in chat_service.py).
 */
export async function sendChatMessage(documentId, question, { topK, history } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      ...(topK ? { top_k: topK } : {}),
      ...(history && history.length > 0 ? { history } : {}),
    }),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't answer right now. Please try again in a moment.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Chat request failed (status ${response.status})`);
  }

  return response.json();
}
