/**
 * Pure decision logic for "which conversation is active" and "what
 * does the sidebar list look like right now" — deliberately kept
 * separate from ChatPage.jsx's data-fetching effects so the actual
 * decisions (not the fetch calls wrapping them) are unit-testable
 * without rendering a component. See conversationSelection.test.js,
 * and documentUploadSync.js for the established precedent this
 * follows.
 *
 * None of these functions mutate their inputs — every one returns a
 * new value built from its arguments only, with no shared module-
 * level state. That's not just a style preference here: it's the
 * actual guarantee behind "conversation A's state can never leak into
 * conversation B" (a named regression requirement for this
 * milestone). A function that remembered anything between calls, or
 * mutated a `conversations` array in place, could let a stale
 * reference from a previous switch bleed into a later one; every test
 * in conversationSelection.test.js that switches between two
 * conversations is really testing for the *absence* of exactly that.
 */

/**
 * Picks which conversation should be active right after the sidebar's
 * list has loaded (GET /conversations — see api/conversations.js),
 * given the id persisted from the user's last session (see
 * utils/persistence.js's loadActiveConversationId).
 *
 * Order of preference:
 *   1. The persisted id, if it's still in the list — the normal case,
 *      restoring exactly where the user left off.
 *   2. Otherwise the first conversation in the list — the backend
 *      already returns these ordered most-recently-active first (see
 *      list_conversations in routes_conversations.py), so this is
 *      "pick up on whatever's most recent" for a persisted id that no
 *      longer resolves (e.g. deleted in another tab/session).
 *   3. `null` when there are no conversations at all yet — the only
 *      case where the caller (ChatPage) needs to create one before
 *      there's anything to make active.
 */
export function resolveActiveConversationId(conversations, persistedId) {
  if (persistedId && conversations.some((conversation) => conversation.id === persistedId)) {
    return persistedId;
  }
  return conversations.length > 0 ? conversations[0].id : null;
}

/**
 * Inserts a freshly created conversation (the response from
 * POST /conversations) at the top of the sidebar list — where it
 * belongs, being the most-recently-active one the instant it's
 * created — without disturbing any other entry already in the list.
 *
 * This is the function that has to prove "New Conversation... must
 * NOT ... overwrite the old conversation" at the list level: every
 * existing entry, in its existing form, must still be present
 * afterward. Deduplicates defensively by id (filtering out any
 * existing entry with the new conversation's id before prepending) in
 * case this is ever called twice for the same response — belt and
 * braces, not a case the current call sites can actually trigger.
 */
export function withNewConversation(conversations, newConversationSummary) {
  const withoutDuplicate = conversations.filter(
    (conversation) => conversation.id !== newConversationSummary.id
  );
  return [newConversationSummary, ...withoutDuplicate];
}

/**
 * After a message send bumps a conversation's `updated_at` server-
 * side (see send_message in routes_conversations.py, which is the
 * only thing that currently touches it — Conversation.updated_at's
 * own docstring names this exact call site), the sidebar should
 * reflect the same "most-recently-active first" ordering GET
 * /conversations would return, without a full round trip just to
 * re-sort a list this client already has. This applies that same
 * update locally: moves the given conversation to the front and
 * updates its `updated_at`, leaving every other entry — including
 * their relative order — untouched.
 *
 * A conversationId that isn't in the list (shouldn't happen — a
 * message can only be sent in a conversation that's already loaded)
 * is a no-op: returns `conversations` back unchanged rather than
 * inventing an entry.
 */
export function touchConversation(conversations, conversationId, updatedAtIso) {
  const match = conversations.find((conversation) => conversation.id === conversationId);
  if (!match) return conversations;

  const touched = { ...match, updated_at: updatedAtIso };
  const rest = conversations.filter((conversation) => conversation.id !== conversationId);
  return [touched, ...rest];
}

/**
 * Removes a deleted conversation (DELETE /conversations/{id} already
 * succeeded server-side — see api/conversations.js's
 * deleteConversation and ChatPage.jsx's handleDeleteConversation,
 * V2.4 Milestone 2 Phase 3 QA fix, issue 1) from the sidebar's local
 * list, leaving every other entry — and their relative order —
 * untouched. Deciding what becomes active afterward is a separate
 * concern the caller handles with resolveActiveConversationId against
 * this function's result (mirroring how creation and deletion are
 * already split into "update the list" vs. "decide what's active" two
 * separate pure steps elsewhere in this module).
 *
 * A conversationId that isn't in the list is a no-op, same reasoning
 * as touchConversation/renameConversationInList's.
 */
export function removeConversationFromList(conversations, conversationId) {
  return conversations.filter((conversation) => conversation.id !== conversationId);
}

/**
 * After a manual rename (PATCH /conversations/{id}) succeeds,
 * updates that conversation's title in the sidebar's local list.
 * Deliberately does *not* reorder the list — unlike touchConversation
 * above, renaming a conversation is not an "activity" event
 * (Conversation.updated_at's own docstring in app/db/models.py is
 * explicit that it's wired to message-sending only, specifically
 * *not* to edits like a rename), so the backend never changes
 * `updated_at` for a rename and this function must match that: same
 * title, same position, every other conversation and field
 * untouched.
 *
 * A conversationId that isn't in the list is a no-op, same reasoning
 * as touchConversation's.
 */
export function renameConversationInList(conversations, conversationId, newTitle) {
  return conversations.map((conversation) =>
    conversation.id === conversationId ? { ...conversation, title: newTitle } : conversation
  );
}
