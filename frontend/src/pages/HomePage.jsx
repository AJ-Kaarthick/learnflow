import { useState } from "react";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import WorkspaceShell from "../components/WorkspaceShell";

// Loads everything already generated for a document in one place, so
// individual panels don't each decide independently when to fetch —
// HomePage coordinates it once and hands each panel its starting data.
// Failures here fall back to empty/null rather than surfacing an
// error: worst case the panel just shows its normal "not generated
// yet" state, which is still a fully working fallback.
async function loadCachedContent(documentId) {
  const [summary, flashcards, quiz, mindmap] = await Promise.all([
    getSummary(documentId).catch(() => null),
    getFlashcards(documentId).catch(() => []),
    getQuiz(documentId).catch(() => []),
    getMindMap(documentId).catch(() => null),
  ]);
  return { summary, flashcards, quiz, mindmap };
}

// HomePage is still a thin composition root: hook extraction is a
// deliberate later milestone, not done here. `openDocument` now
// includes the automatic single-document chat sync added in this
// polish pass (see its comment) — everything else is unchanged from
// the V2.1 workspace milestone.
function HomePage() {
  // Bumped whenever an action outside LibraryPanel's own search/sort
  // controls changes the underlying document data (open, rename,
  // delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  const [document, setDocument] = useState(null);
  const [cachedContent, setCachedContent] = useState(null);
  const [contentLoading, setContentLoading] = useState(false);

  // Documents currently included in the chat conversation in the right
  // panel. Kept as its own piece of state rather than always being
  // derived from `document` because multi-document mode (2+ manually
  // checked) is explicit and independent of whichever single document
  // is open in the center panel — see openDocument for how the two
  // stay in sync in the common single-document case. Holds
  // {id, original_filename} rather than bare ids so the assistant
  // panel can show readable chips without needing LibraryPanel to
  // expose its whole fetched list.
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  function handleToggleSelect(doc) {
    setSelectedDocuments((previous) => {
      const isSelected = previous.some((selected) => selected.id === doc.id);
      if (isSelected) {
        return previous.filter((selected) => selected.id !== doc.id);
      }
      return [...previous, { id: doc.id, original_filename: doc.original_filename }];
    });
  }

  async function openDocument(doc) {
    setDocument(doc);
    setCachedContent(null);

    // Automatic single-document chat selection: clicking a document
    // makes it both the active study document AND the active chat
    // document, and switching documents switches the conversation with
    // it — no separate checkbox click required for the common case.
    //
    // "Multi-document mode" isn't a separate flag — it's derived from
    // selectedDocuments itself: 0 or 1 selected is "single/automatic"
    // mode, where opening a document keeps the two in sync; 2+ selected
    // (only reachable by manually checking a second box — see
    // handleToggleSelect) is "multi-document mode", where the selection
    // is entirely explicit and opening a document to peek at its study
    // tools must NOT silently derail an in-progress multi-document
    // conversation. Unchecking back down to one document (or deleting
    // one — see handleDelete) drops the count back to <=1 with no
    // special-case code needed, which is exactly "leaving multi-
    // document mode automatically returns to single-document behavior":
    // it's the same rule, just read the other direction.
    setSelectedDocuments((previous) =>
      previous.length <= 1
        ? [{ id: doc.id, original_filename: doc.original_filename }]
        : previous
    );

    // Timestamp the open server-side (powers the "Recently Opened"
    // sort) and refresh the library so it reflects the new order.
    // Best-effort: if this fails, opening the document should still
    // work normally.
    markDocumentOpened(doc.id)
      .catch(() => {})
      .finally(() => setRefreshSignal((count) => count + 1));

    if (doc.status !== "ready") return;
    setContentLoading(true);
    const content = await loadCachedContent(doc.id);
    setCachedContent(content);
    setContentLoading(false);
  }

  async function handleUploadComplete(newDocument) {
    await openDocument(newDocument);
    // openDocument's automatic sync above only replaces the selection
    // with [newDocument] in single/automatic mode (0 or 1 previously
    // selected) — in multi-document mode it deliberately leaves the
    // existing selection untouched (see openDocument's comment), which
    // for an upload isn't what we want: uploading a new file is an
    // unambiguous "include this too", not a reason to derail an
    // existing multi-document conversation. This patches it in for
    // that case; in single/automatic mode it's already there and this
    // is a no-op.
    setSelectedDocuments((previous) =>
      previous.some((selected) => selected.id === newDocument.id)
        ? previous
        : [...previous, { id: newDocument.id, original_filename: newDocument.original_filename }]
    );
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setDocument((previous) => (previous && previous.id === documentId ? updated : previous));
    setSelectedDocuments((previous) =>
      previous.map((selected) =>
        selected.id === documentId
          ? { ...selected, original_filename: updated.original_filename }
          : selected
      )
    );
    setRefreshSignal((count) => count + 1);
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    if (document && document.id === documentId) {
      setDocument(null);
      setCachedContent(null);
    }
    setSelectedDocuments((previous) => previous.filter((selected) => selected.id !== documentId));
    setRefreshSignal((count) => count + 1);
  }

  return (
    <WorkspaceShell
      refreshSignal={refreshSignal}
      document={document}
      selectedDocuments={selectedDocuments}
      contentLoading={contentLoading}
      cachedContent={cachedContent}
      onOpen={openDocument}
      onRename={handleRename}
      onDelete={handleDelete}
      onToggleSelect={handleToggleSelect}
      onUploadComplete={handleUploadComplete}
    />
  );
}

export default HomePage;
