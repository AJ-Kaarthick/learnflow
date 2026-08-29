/**
 * Resolves a conversation's associated documents (ConversationDocumentSummary[]
 * — id, original_filename, status; see schemas/conversation.py) into
 * the full DocumentResponse records ChatPage's chip-building
 * (toDocumentChip, utils/documentChip.js) actually needs.
 *
 * This exists because of a gap in what the conversation endpoints
 * return: ConversationDocumentSummary deliberately omits
 * `character_count` ("just enough for the frontend to render a
 * document chip", per that schema's own docstring) — but
 * character_count is exactly what documentReadiness.hasNoReadableText
 * needs to tell a readable document from an unreadable one. Building
 * chips straight from a conversation's `documents` array would make
 * every document look readable regardless of its real content — the
 * same class of bug documentChip.js's own docstring describes for a
 * different missing-field case. So ChatPage always re-hydrates a
 * conversation's document ids through GET /documents/{id} (see
 * utils/documentHydration.js, already used for this exact purpose
 * pre-Milestone-2) before building chips, and this function is the
 * "put the hydrated records back in the right order" step of that —
 * hydrateDocumentIds explicitly does not guarantee order (parallel
 * fetches), and a reshuffling chip row on every conversation switch
 * would be a visible regression.
 */
export function orderHydratedDocuments(documentSummaries, hydratedDocuments) {
  const hydratedById = new Map(hydratedDocuments.map((document) => [document.id, document]));
  return (documentSummaries ?? [])
    .filter((summary) => hydratedById.has(summary.id))
    .map((summary) => hydratedById.get(summary.id));
}
