import { useEffect, useRef, useState } from "react";
import { deleteDocument, getDocument, markDocumentOpened, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import WorkspaceShell from "../components/WorkspaceShell";
import { mergeGeneratedContent } from "../utils/cachedContent";
import {
  loadActiveDocumentId,
  loadSelectedDocumentIds,
  saveActiveDocumentId,
  saveSelectedDocumentIds,
} from "../utils/persistence";

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

  // Guards the two "persist on change" effects below so the very
  // first render — before restoreWorkspace (below) has had a chance
  // to run — doesn't immediately overwrite last session's saved
  // document/selection with this render's still-empty initial state.
  // Flipped to true once restoreWorkspace finishes, whether or not it
  // found anything to restore.
  const hasRestoredRef = useRef(false);

  // Restores the previous session's active document and selected
  // documents on first mount (V2.1 Milestone 2, features 1 & 6).
  // Runs once: fetches only the documents actually referenced by
  // saved state (not the whole library), and drops any id that no
  // longer resolves (the document was deleted in a previous session)
  // both from what gets restored here and from what stays in storage,
  // so a stale id doesn't linger forever.
  useEffect(() => {
    let cancelled = false;

    async function restoreWorkspace() {
      try {
        const persistedActiveId = loadActiveDocumentId();
        const persistedSelectedIds = loadSelectedDocumentIds();
        const idsToFetch = Array.from(
          new Set([...(persistedSelectedIds || []), persistedActiveId].filter(Boolean))
        );
        if (idsToFetch.length === 0) return;

        const results = await Promise.allSettled(idsToFetch.map((id) => getDocument(id)));
        if (cancelled) return;

        const foundById = new Map();
        results.forEach((result, index) => {
          if (result.status === "fulfilled") {
            foundById.set(idsToFetch[index], result.value);
          }
        });

        const restoredSelected = (persistedSelectedIds || [])
          .filter((id) => foundById.has(id))
          .map((id) => {
            const doc = foundById.get(id);
            return { id: doc.id, original_filename: doc.original_filename };
          });
        if (restoredSelected.length > 0) {
          setSelectedDocuments(restoredSelected);
        }
        if (restoredSelected.length !== (persistedSelectedIds || []).length) {
          saveSelectedDocumentIds(restoredSelected.map((doc) => doc.id));
        }

        if (persistedActiveId && foundById.has(persistedActiveId)) {
          const activeDoc = foundById.get(persistedActiveId);
          setDocument(activeDoc);
          if (activeDoc.status === "ready") {
            setContentLoading(true);
            const content = await loadCachedContent(activeDoc.id);
            if (!cancelled) {
              setCachedContent(content);
              setContentLoading(false);
            }
          }
        } else if (persistedActiveId) {
          // The previously active document is gone — nothing to
          // restore it to, and no point keeping the stale id around.
          saveActiveDocumentId(null);
        }
      } finally {
        if (!cancelled) hasRestoredRef.current = true;
      }
    }

    restoreWorkspace();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keeps storage in sync with the live active document / selection
  // as the user works, so the *next* refresh restores wherever they
  // ended up — not just wherever restoreWorkspace found them.
  useEffect(() => {
    if (!hasRestoredRef.current) return;
    saveActiveDocumentId(document?.id ?? null);
  }, [document]);

  useEffect(() => {
    if (!hasRestoredRef.current) return;
    saveSelectedDocumentIds(selectedDocuments.map((selected) => selected.id));
  }, [selectedDocuments]);

  // Merges a freshly generated result back into cachedContent, the
  // single place StudyWorkspace's panels read their starting data
  // from (see StudyWorkspace.jsx). Without this, cachedContent stays
  // whatever it was when the document was opened: each panel only
  // ever kept its own generated content in local component state, and
  // StudyWorkspace only renders the *active* tab's panel — switching
  // away unmounts it, so switching back remounted it from that same
  // stale cachedContent, and the just-generated content looked like
  // it had vanished (even though the backend still had it, which is
  // why a full refresh — which re-fetches cachedContent from
  // scratch — always showed it correctly). This keeps cachedContent
  // as the one source of truth panels are (re)initialized from,
  // instead of adding a second, parallel cache.
  function handleContentGenerated(kind, value) {
    setCachedContent((previous) => mergeGeneratedContent(previous, kind, value));
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
      onContentGenerated={handleContentGenerated}
      onOpen={openDocument}
      onRename={handleRename}
      onDelete={handleDelete}
      onToggleSelect={handleToggleSelect}
      onUploadComplete={handleUploadComplete}
    />
  );
}

export default HomePage;
