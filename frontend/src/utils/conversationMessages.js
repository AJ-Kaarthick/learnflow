/**
 * Pure conversion between the backend's persisted message shape
 * (MessageResponse — see schemas/conversation.py: id, role, content,
 * position, created_at, sources, grounded) and the plain object shape
 * ChatPanel already renders (id, role, content, sources, createdAt as
 * an epoch-ms number for formatTimestamp, isError). Extracted into its
 * own module — rather than left as inline mapping inside ChatPanel,
 * the way the old `${Date.now()}-assistant` message objects were built
 * — specifically so it's unit-testable without rendering a component
 * (this project's frontend test suite is plain `node --test`, with no
 * JSX transform — see documentUploadSync.test.js for the established
 * precedent).
 *
 * Nothing here calls the network. ChatPage/ChatPanel own when to call
 * api/conversations.js; this module only ever transforms whatever
 * response those calls already returned.
 */

/**
 * One persisted message -> ChatPanel's internal shape.
 *
 * `createdAt` becomes an epoch-ms number (Date.parse of the backend's
 * ISO 8601 `created_at`) because that's what ChatMessageBubble's
 * formatTimestamp already expects — it previously only ever received
 * `Date.now()` for client-optimistic messages, never a parsed
 * timestamp, so this is the first call site that needs the
 * conversion. Falls back to `null` if `created_at` is missing or
 * unparsable, which formatTimestamp already treats as "don't show a
 * timestamp" rather than crashing.
 *
 * `sources` stays `null`/`undefined` through untouched when the
 * backend sent none — ChatMessageBubble's own
 * `message.sources && message.sources.length > 0` guard already
 * handles that, so there's nothing to normalize here.
 */
export function toInternalMessage(message) {
  const parsed = message.created_at ? Date.parse(message.created_at) : NaN;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    sources: message.sources,
    grounded: message.grounded,
    createdAt: Number.isNaN(parsed) ? null : parsed,
  };
}

/**
 * A full conversation's persisted messages (already in `position`
 * order from the backend — see routes_conversations.py's
 * `_message_responses`) -> the array ChatPanel's `messages` state
 * initializes from when a conversation is opened or switched into.
 *
 * Deliberately returns a brand-new array built only from `messages`,
 * touching nothing else — this is the function that has to prove
 * "conversation A's state can never leak into conversation B": called
 * twice with two different conversations' messages, in either order,
 * it must produce two independent results with no shared references
 * and no memory of the previous call. See
 * conversationMessages.test.js's "no cross-conversation leakage" case.
 */
export function toInternalMessages(messages) {
  return (messages ?? []).map(toInternalMessage);
}

/**
 * Folds a just-sent turn (ConversationMessageResponse: `{ user_message,
 * assistant_message }`, both already persisted server-side — see
 * send_message in routes_conversations.py) into the current message
 * list, replacing the optimistic, client-only user-message placeholder
 * ChatPanel appended the instant the user hit Send.
 *
 * Replacing (rather than just appending the assistant reply after the
 * still-optimistic user bubble, which is what the old localStorage-era
 * ChatPanel did) means the user message ChatPanel ends up showing has
 * a real, backend-assigned id, position, and timestamp — the same
 * "server response is a receipt for the fresher local state" idea
 * `sources`/`grounded` already relied on, just applied to the user
 * turn too. `optimisticId` not being found (e.g. it was already
 * cleared some other way) degrades gracefully: both persisted messages
 * are still appended, just without anything removed first.
 */
export function appendPersistedTurn(messages, response, optimisticId) {
  const withoutOptimistic = messages.filter((message) => message.id !== optimisticId);
  return [
    ...withoutOptimistic,
    toInternalMessage(response.user_message),
    toInternalMessage(response.assistant_message),
  ];
}
