import { toDocumentChip } from "./documentChip.js";

/**
 * Computes everything ChatPage.handleUploadComplete needs to do once
 * a document finishes uploading: how the current chat selection
 * changes, and whether the Document Library must be told to re-fetch
 * so the new document actually shows up there.
 *
 * BUG THIS FIXES: after uploading from the Chat page, the new
 * document appeared in Study's Document Library immediately but not
 * in Chat's — only after a full page refresh, or switching to Study
 * and back. Root cause: LibraryPanel (used by both pages) only
 * re-fetches its document list when its `refreshSignal` prop changes
 * (see LibraryPanel.jsx's `[search, sort, refreshSignal]` effect).
 * StudyPage's handleUploadComplete routes through handleOpenDocument,
 * which already bumps refreshSignal via markDocumentOpened's
 * `.finally()`. ChatPage's handleUploadComplete only ever updated its
 * own `selectedDocuments` chat-selection state — nothing told
 * LibraryPanel a new document existed, so it kept showing whatever it
 * had fetched before the upload until something else (opening a
 * document, renaming, deleting, or remounting the page) happened to
 * bump refreshSignal for an unrelated reason.
 *
 * `shouldRefreshLibrary` here is always `true`: a completed upload
 * always changes the underlying document list, regardless of how it
 * affects the current chat selection below. It's still returned
 * explicitly (rather than left implicit in the caller) so that
 * invariant is a documented, tested contract — the same reasoning
 * documentChip.js gives for extracting toDocumentChip — instead of
 * something only reachable, and only breakable, through full
 * component rendering.
 *
 * BUG THIS FIXES (V2.4 Milestone 2 Phase 3 QA, issue 4): uploading a
 * new document from Chat's "Add documents" picker while a conversation
 * already had exactly one document selected (e.g. Linux-Tutorial.pdf)
 * silently *replaced* that selection with just the new upload, instead
 * of adding the new document alongside it. Root cause: this function
 * used to borrow ChatPage's `handleOpenForChat` rule ("click = single,
 * checkbox = add another", i.e. 0-or-1-selected replaces, 2+ appends)
 * for uploads too. That rule is correct for *opening* an existing
 * document from the library — clicking a document is "make this my
 * one thing to chat with" — but an *upload* is a different action with
 * a different intent: the user was already mid-conversation and
 * explicitly asked to add a new document to it, never to replace what
 * was already selected. A brand-new upload is therefore always merged
 * into the existing selection, regardless of how many documents were
 * already selected — the only thing that changes the *count* of
 * previously selected documents here is if the same document was
 * somehow already selected (a re-upload), which is deduplicated rather
 * than added twice, exactly as it already was in multi-document mode.
 */
export function resolveChatUploadSync(previousSelectedDocuments, newDocument) {
  const alreadySelected = previousSelectedDocuments.some(
    (selected) => selected.id === newDocument.id
  );

  const selectedDocuments = alreadySelected
    ? previousSelectedDocuments
    : [...previousSelectedDocuments, toDocumentChip(newDocument)];

  return { selectedDocuments, shouldRefreshLibrary: true };
}
