/**
 * Whether a "ready" document has nothing readable/extractable in it —
 * e.g. a scanned or image-only PDF/PPTX/DOCX where OCR (or the
 * extractor) found no characters at all. This is the same signal the
 * backend already uses to gate Chat/RAG indexing (see
 * routes_rag.py's _get_ready_document and routes_chat.py's
 * _get_indexed_document: `not (document.extracted_text or "").strip()`)
 * and now also uses to gate Summary/Flashcards/Quiz/Mind Map
 * generation (see each routes_*.py's own _get_ready_document).
 *
 * The frontend never receives the raw extracted_text itself (see
 * DocumentResponse.from_document in the backend, which only sends a
 * preview + a count) — character_count is exactly `len(extracted_text
 * or "")`, so `=== 0` is the frontend-side equivalent of the
 * backend's `not extracted_text.strip()` check for the common case
 * (nothing extracted at all). This intentionally doesn't try to
 * detect a whitespace-only document client-side; that's an edge case
 * only reachable by seeding data directly (see the backend tests),
 * not by anything the real upload/extraction pipeline produces, and
 * the backend's own guard (still authoritative) covers it regardless
 * of what this client-side check decides.
 *
 * Only meaningful once a document has actually finished processing
 * ("ready") — a still-processing or failed document is a different,
 * already-handled state (see StudyWorkspace's own status handling).
 *
 * Used to gate Study generation (Summary/Flashcards/Quiz/Mind Map) on
 * the frontend *before* ever calling the API — see
 * NoReadableTextState.jsx and StudyWorkspace.jsx — so a document
 * already known to have nothing readable in it never triggers a
 * wasted network round trip, let alone an AI request. Chat's
 * equivalent check lives entirely server-side (routes_chat.py) and is
 * intentionally left as-is; this only covers the Study tools.
 */
export function hasNoReadableText(document) {
  return Boolean(document) && document.status === "ready" && document.character_count === 0;
}

/**
 * Splits a list of selected documents (e.g. Chat's multi-document
 * selection) into the ones usable for chat/RAG and the ones that
 * aren't, using the exact same per-document signal as hasNoReadableText
 * above — no separate detection for Chat's multi-document case.
 *
 * Order is preserved within each group. Deliberately returns two
 * plain arrays (not e.g. a Map keyed by id) because both call sites
 * that need this (ChatPanel: which ids to index/chat with vs. which
 * filenames to warn about) just want to iterate one group or the
 * other, not look anything up by id.
 */
export function splitDocumentsByReadability(documents) {
  const readable = [];
  const unreadable = [];
  for (const document of documents ?? []) {
    (hasNoReadableText(document) ? unreadable : readable).push(document);
  }
  return { readable, unreadable };
}

// Oxford-comma joiner for filenames in describeUnreadableDocuments
// below — "A" / "A and B" / "A, B, and C". Not exported: it's a pure
// formatting detail of that one message, not a general-purpose list
// utility anything else in the app currently needs.
function joinFilenames(filenames) {
  if (filenames.length === 1) return filenames[0];
  if (filenames.length === 2) return `${filenames[0]} and ${filenames[1]}`;
  return `${filenames.slice(0, -1).join(", ")}, and ${filenames[filenames.length - 1]}`;
}

/**
 * Builds the Chat UX-polish message (V2.4 Milestone 1, issue 2) that
 * replaces the old ambiguous "this document has no readable text"
 * wording — see routes_chat.py's _get_indexed_document and
 * routes_rag.py's _get_ready_document, whose error text never named a
 * file (or, for routes_chat.py's version, only ever named a raw
 * document id) and, when multiple documents were selected, blocked
 * every one of them rather than just the unreadable one.
 *
 * Takes the *unreadable* group from splitDocumentsByReadability and
 * how many *readable* documents remain in the same selection, and
 * returns one sentence-pair covering all three things a user needs to
 * immediately understand (see the V2.4 Milestone 1 brief, requirement
 * 10): which document(s) are unavailable (their actual filenames, via
 * original_filename — never a document id), why (no readable text),
 * and — only when it's actually true — that the rest of their
 * selection still works. Returns null when there's nothing to report
 * (an empty unreadable list), so callers can use it directly as a
 * conditional-render guard.
 */
export function describeUnreadableDocuments(unreadableDocuments, readableCount) {
  if (!unreadableDocuments || unreadableDocuments.length === 0) {
    return null;
  }

  const isPlural = unreadableDocuments.length > 1;
  const filenames = joinFilenames(unreadableDocuments.map((document) => document.original_filename));

  const whatAndWhy = isPlural
    ? `${filenames} have no readable text, so LearnFlow can't use them for chat.`
    : `${filenames} has no readable text, so LearnFlow can't use it for chat.`;

  if (readableCount === 0) {
    return `${whatAndWhy} Select a document with readable text to start chatting.`;
  }

  const reassurance =
    readableCount === 1
      ? "The other document you selected is still available to chat with."
      : "The other documents you selected are still available to chat with.";

  return `${whatAndWhy} ${reassurance}`;
}
