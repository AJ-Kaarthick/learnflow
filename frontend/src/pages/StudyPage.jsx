import { useEffect, useRef, useState } from "react";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import LibraryPanel from "../components/LibraryPanel";
import StudyWorkspace from "../components/StudyWorkspace";
import { mergeGeneratedContent } from "../utils/cachedContent";
import { hydrateDocumentIds } from "../utils/documentHydration";
import { loadActiveDocumentId, saveActiveDocumentId } from "../utils/persistence";

// Loads everything already generated for a document in one place, so
// individual panels don't each decide independently when to fetch —
// this page coordinates it once and hands each panel its starting
// data. Failures here fall back to empty/null rather than surfacing
// an error: worst case the panel just shows its normal "not generated
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

// V2.4 Milestone 1: this is what's left of the old combined HomePage
// once the permanent AI Assistant panel — and everything that existed
// only to keep it in sync with whatever document was open (see the
// old openDocument's automatic-chat-selection comment, now gone) —
// moves to its own page (ChatPage.jsx). Study and Chat now restore
// and persist their own halves of workspace state independently
// (`activeDocumentId` here, `selectedDocumentIds` in ChatPage) rather
// than one page owning both and syncing them, which persistence.js
// already stored as two separate fields even before this milestone —
// so nothing about the storage schema needed to change, only which
// component reads/writes each piece.
function StudyPage() {
  // Bumped whenever an action outside LibraryPanel's own search/sort
  // controls changes the underlying document data (open, rename,
  // delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  const [document, setDocument] = useState(null);
  const [cachedContent, setCachedContent] = useState(null);
  const [contentLoading, setContentLoading] = useState(false);

  // Guards the "persist on change" effect below so the very first
  // render — before restoreActiveDocument (below) has had a chance to
  // run — doesn't immediately overwrite last session's saved active
  // document with this render's still-empty initial state.
  const hasRestoredRef = useRef(false);

  // Restores the previous session's active study document on first
  // mount. Drops the id (both from what gets restored and from what
  // stays in storage) if it no longer resolves — the document was
  // deleted in a previous session — so a stale id doesn't linger
  // forever.
  useEffect(() => {
    let cancelled = false;

    async function restoreActiveDocument() {
      try {
        const persistedActiveId = loadActiveDocumentId();
        if (!persistedActiveId) return;

        const [activeDoc] = await hydrateDocumentIds([persistedActiveId]);
        if (cancelled) return;

        if (activeDoc) {
          setDocument(activeDoc);
          if (activeDoc.status === "ready") {
            setContentLoading(true);
            const content = await loadCachedContent(activeDoc.id);
            if (!cancelled) {
              setCachedContent(content);
              setContentLoading(false);
            }
          }
        } else {
          // The previously active document is gone — nothing to
          // restore it to, and no point keeping the stale id around.
          saveActiveDocumentId(null);
        }
      } finally {
        if (!cancelled) hasRestoredRef.current = true;
      }
    }

    restoreActiveDocument();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keeps storage in sync with the live active document as the user
  // works, so the *next* refresh restores wherever they ended up —
  // not just wherever restoreActiveDocument found them.
  useEffect(() => {
    if (!hasRestoredRef.current) return;
    saveActiveDocumentId(document?.id ?? null);
  }, [document]);

  // Merges a freshly generated result back into cachedContent, the
  // single place StudyWorkspace's panels read their starting data
  // from. Without this, cachedContent stays whatever it was when the
  // document was opened — see the equivalent comment on the old
  // HomePage for the full history of why this exists.
  function handleContentGenerated(kind, value) {
    setCachedContent((previous) => mergeGeneratedContent(previous, kind, value));
  }

  async function handleOpenDocument(doc) {
    setDocument(doc);
    setCachedContent(null);

    // Timestamp the open server-side (powers the "Recently Opened"
    // sort, and Home's "Continue studying" list) and refresh the
    // library so it reflects the new order. Best-effort: if this
    // fails, opening the document should still work normally.
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
    await handleOpenDocument(newDocument);
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setDocument((previous) => (previous && previous.id === documentId ? updated : previous));
    setRefreshSignal((count) => count + 1);
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    if (document && document.id === documentId) {
      setDocument(null);
      setCachedContent(null);
    }
    setRefreshSignal((count) => count + 1);
  }

  return (
    <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
      <aside
        aria-label="Document library"
        className="min-w-0 shrink-0 border-b border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[22%] lg:min-w-[260px] lg:max-w-[360px] lg:overflow-hidden lg:border-b-0 lg:border-r lg:p-8"
      >
        <LibraryPanel
          refreshSignal={refreshSignal}
          activeDocumentId={document?.id ?? null}
          selectable={false}
          onOpen={handleOpenDocument}
          onRename={handleRename}
          onDelete={handleDelete}
          onUploadComplete={handleUploadComplete}
        />
      </aside>

      {/* No more fixed-width chat column reserving ~26% of the
          screen (see the old WorkspaceShell) — Study now gets
          everything the library doesn't need, which is the whole
          point of this milestone's "significantly more space for the
          selected study material". */}
      {/* No `id`/`tabIndex` here for a skip-link target anymore —
          AppShell's skip link now focuses its own `#page-content`
          wrapper (see AppShell.jsx), which works the same way
          regardless of which page is mounted inside it, rather than
          each page needing to expose an identically-named landmark. */}
      <main
        aria-label="Study workspace"
        className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-y-auto lg:p-10"
      >
        <StudyWorkspace
          document={document}
          contentLoading={contentLoading}
          cachedContent={cachedContent}
          onContentGenerated={handleContentGenerated}
        />
      </main>
    </div>
  );
}

export default StudyPage;
