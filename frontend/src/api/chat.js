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
 *
 * `signal` is an optional AbortSignal (Milestone 4's "Stop
 * generation") — this endpoint isn't streamed, so there's no partial
 * output to interrupt mid-token; aborting just stops the client from
 * waiting on/using the eventual response. The backend request may
 * still complete server-side; nothing here cancels that.
 */
export async function sendChatMessage(documentId, question, { topK, history, signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      ...(topK ? { top_k: topK } : {}),
      ...(history && history.length > 0 ? { history } : {}),
    }),
    signal,
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

/**
 * Same idea as sendChatMessage, but grounded across several documents
 * at once (POST /documents/chat, not scoped to one document id) — for
 * questions like "compare X and Y" where the answer may draw on more
 * than one selected document. Each returned source includes which
 * document it came from (document_id/document_name), which
 * sendChatMessage's sources don't need since there's only one document
 * to begin with.
 */
export async function sendMultiDocumentChatMessage(documentIds, question, { topK, history, signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_ids: documentIds,
      question,
      ...(topK ? { top_k: topK } : {}),
      ...(history && history.length > 0 ? { history } : {}),
    }),
    signal,
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
