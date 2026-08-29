import { API_BASE_URL } from "./config";

/**
 * The frontend counterpart to `app/api/v1/routes_conversations.py`
 * (backend V2.4 Milestone 2, phases 1–2 — already implemented and
 * covered by `backend/tests/test_conversations.py` and
 * `test_conversation_messages.py`). This module is deliberately thin:
 * each function is a direct 1:1 call to one route, with no logic of
 * its own — anything that decides *which* conversation should be
 * active, or how a response should be merged into UI state, lives in
 * `utils/conversationSelection.js`, `utils/conversationMessages.js`,
 * and `utils/conversationDocuments.js` instead, so that decision logic
 * stays plain and unit-testable (see this project's existing
 * convention — api/chat.js and api/documents.js are equally thin, all
 * the "what do we do with the response" logic lives in components or
 * utils).
 *
 * This phase wires up what the frontend Conversation Management
 * foundation needs: listing, fetching, creating, associating
 * documents, renaming, sending a message, and (V2.4 Milestone 2
 * Phase 3 QA fix, issue 1) deleting a conversation — the backend
 * route (DELETE /conversations/{id}) already existed and was already
 * covered by backend/tests/test_conversations.py, but had no frontend
 * entry point until this fix (see deleteConversation below and
 * ChatPage.jsx's handleDeleteConversation).
 */

async function parseErrorDetail(response, fallback) {
  const errorBody = await response.json().catch(() => null);
  return errorBody?.detail || fallback;
}

/**
 * GET /conversations — the list/sidebar. Ordered by the backend,
 * most-recently-active first (see ConversationSummaryResponse's
 * docstring); this function doesn't re-sort.
 */
export async function listConversations() {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`);

  if (!response.ok) {
    throw new Error(`Could not load conversations (status ${response.status})`);
  }

  return response.json();
}

/**
 * GET /conversations/{id} — full detail (metadata + documents +
 * messages) for restoring a conversation, whether that's switching to
 * it from the sidebar or restoring the last-active one after a
 * refresh (see utils/persistence.js's loadActiveConversationId).
 */
export async function getConversation(conversationId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}`);

  if (!response.ok) {
    throw new Error(`Could not load this conversation (status ${response.status})`);
  }

  return response.json();
}

/**
 * POST /conversations — creates a new, independent conversation.
 * `documentIds` is optional (defaults to none), for the "New
 * Conversation" action, which deliberately starts empty rather than
 * inheriting whatever was selected in the conversation being left —
 * see ChatPage.jsx's handleCreateConversation.
 */
export async function createConversation(documentIds = []) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response, `Could not create a new conversation (status ${response.status})`));
  }

  return response.json();
}

/**
 * PUT /conversations/{id}/documents — replaces a conversation's
 * entire associated document set. Used for both "open this document
 * for chat" (single-element list) and toggling a document in/out of
 * an in-progress multi-document conversation (see ChatPage.jsx) —
 * both are "here is the full desired set" calls, matching how
 * LibraryPanel's selection state already works.
 */
export async function replaceConversationDocuments(conversationId, documentIds) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}/documents`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });

  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Could not update this conversation's documents (status ${response.status})`)
    );
  }

  return response.json();
}

/**
 * PATCH /conversations/{id} — manually renames a conversation.
 * Returns the updated ConversationSummaryResponse (no documents/
 * messages — a rename never touches either). Always marks the
 * conversation `title_is_custom` server-side, which is what would
 * protect a manual rename from being overwritten if/when AI-generated
 * titles (explicitly deferred — see this milestone's brief) are added
 * later; nothing about that is this function's concern.
 */
export async function renameConversation(conversationId, title) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response, `Could not rename this conversation (status ${response.status})`));
  }

  return response.json();
}

/**
 * DELETE /conversations/{id} — permanently deletes a conversation and
 * everything that belongs only to it (its messages, its document
 * associations). Never touches the documents themselves — see
 * delete_conversation's docstring in routes_conversations.py, which
 * only removes the join rows pointing at them. A 204 with no body on
 * success; ChatPage.handleDeleteConversation is what decides what the
 * sidebar/active conversation should look like afterward (removing it
 * from the local list, and — if it was the active one — switching to
 * another conversation or starting a fresh one).
 */
export async function deleteConversation(conversationId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Could not delete this conversation (status ${response.status})`)
    );
  }
}

/**
 * POST /conversations/{id}/messages — sends one message in a
 * persistent conversation. Unlike the old sendChatMessage/
 * sendMultiDocumentChatMessage (api/chat.js), there's no `history` to
 * pass — the backend loads it from the database itself (that's the
 * entire point of Milestone 2) — and no `document_ids` either, since
 * the conversation's own associations determine scope. Returns both
 * persisted messages (user + assistant) in one round trip; see
 * utils/conversationMessages.js for how ChatPanel folds that into its
 * message list.
 *
 * `signal` is an optional AbortSignal (same "Stop generation" support
 * api/chat.js's functions have) — this endpoint isn't streamed, so
 * aborting just stops the client from waiting on the response. As
 * with the old endpoints, the backend request may still complete
 * (and, now, still get persisted) server-side; nothing here cancels
 * that.
 */
export async function sendConversationMessage(conversationId, content, { topK, signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content,
      ...(topK ? { top_k: topK } : {}),
    }),
    signal,
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't answer right now. Please try again in a moment.");
    }
    throw new Error(await parseErrorDetail(response, `Chat request failed (status ${response.status})`));
  }

  return response.json();
}
