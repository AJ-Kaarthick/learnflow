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
 */
export function resolveChatUploadSync(previousSelectedDocuments, newDocument) {
  const alreadySelected = previousSelectedDocuments.some(
    (selected) => selected.id === newDocument.id
  );

  // Same "click = single, checkbox = add another" reasoning as
  // ChatPage's handleOpenForChat: in single/automatic mode (0 or 1
  // selected) a new upload replaces the selection; in multi-document
  // mode it's appended rather than derailing an in-progress
  // conversation, unless it's already selected (re-uploading the same
  // document shouldn't duplicate its chip).
  const selectedDocuments =
    previousSelectedDocuments.length <= 1
      ? [toDocumentChip(newDocument)]
      : alreadySelected
        ? previousSelectedDocuments
        : [...previousSelectedDocuments, toDocumentChip(newDocument)];

  return { selectedDocuments, shouldRefreshLibrary: true };
}
