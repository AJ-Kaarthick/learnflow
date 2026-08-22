/**
 * Builds the minimal per-document record ChatPage keeps in its
 * `selectedDocuments` state — the same object that flows, unmodified,
 * all the way down into AssistantPanel's chip row and ChatPanel's
 * `documents` prop (see ChatPage.jsx and ChatPanel.jsx).
 *
 * MUST include every field documentReadiness.hasNoReadableText needs
 * (`status`, `character_count`) alongside the two fields the chip UI
 * actually displays (`id`, `original_filename`). Dropping either
 * readiness field here silently makes every selected document look
 * readable to ChatPanel, regardless of its real status — which was
 * the actual root cause of a real, manually-reported bug: the Chat
 * UX polish fix that filters an unreadable document out of
 * indexing/chat requests (see ChatPanel.jsx's
 * splitDocumentsByReadability usage) was correct in isolation, but
 * never saw a real unreadable document in production, because this
 * function used to build a chip with only {id, original_filename}.
 * With no readiness fields on it, hasNoReadableText(chip) was always
 * false, every selected document — readable or not — went into
 * ChatPanel's single Promise.all indexing call, and one unreadable
 * document among them still turned into the old ambiguous, every-
 * document-blocked global error.
 *
 * Every call site that builds a chip (library selection, upload,
 * rename, restoring a persisted selection on page load — see
 * ChatPage.jsx) already has the full DocumentResponse shape in hand
 * (id, original_filename, status, character_count, ...; see
 * api/documents.js and DocumentResponse in the backend), so this is
 * purely about which fields get kept, never about fetching anything
 * new — no new detection, per requirement 8.
 *
 * Extracted into its own module (rather than staying a private
 * function inside ChatPage.jsx) specifically so this contract is
 * unit-testable directly — see documentChip.test.js — instead of
 * only reachable through full component rendering. That gap (a
 * correct utility function, and a correct consuming component, with
 * an untested piece of glue silently dropping data between them) is
 * exactly how the regression above shipped past the previous fix's
 * test suite.
 */
export function toDocumentChip(document) {
  return {
    id: document.id,
    original_filename: document.original_filename,
    status: document.status,
    character_count: document.character_count,
  };
}
