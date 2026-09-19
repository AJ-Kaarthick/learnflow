import { useEffect, useRef, useState } from "react";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import LibraryPanel from "../components/LibraryPanel";
import Modal from "../components/Modal";
import StudyWorkspace from "../components/StudyWorkspace";
import { mergeGeneratedContent } from "../utils/cachedContent";
import { hydrateDocumentIds } from "../utils/documentHydration";
import {
  loadActiveDocumentId,
  loadSelectedStudyDocumentIds,
  saveActiveDocumentId,
  saveSelectedStudyDocumentIds,
} from "../utils/persistence";
import {
  MAX_STUDY_DOCUMENTS,
  openStudyDocument,
  removeStudyDocument,
  resolveActiveStudyDocument,
  syncStudyUpload,
  toggleStudyDocument,
} from "../utils/studySelection";

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

// V3 Milestone 3 (Phase 1): Multi-Document Study Foundation
// Supports selecting and working with 1–10 documents in the study
// workspace while preserving the single-document study behavior.
function StudyPage() {
  // Bumped whenever an action outside LibraryPanel's own search/sort
  // controls changes the underlying document data (open, rename,
  // delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  // The collection of currently selected study documents (1 to 10).
  const [selectedDocuments, setSelectedDocuments] = useState([]);
  // The currently focused document (whose individual study tools are shown).
  const [document, setDocument] = useState(null);
  const [cachedContent, setCachedContent] = useState(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [selectionError, setSelectionError] = useState(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  // Guards the "persist on change" effect below so the very first
  // render — before restoreActiveStudySession has had a chance to
  // run — doesn't immediately overwrite last session's saved state.
  const hasRestoredRef = useRef(false);

  // Restores the previous session's study document selection on mount.
  useEffect(() => {
    let cancelled = false;

    async function restoreActiveStudySession() {
      try {
        const persistedIds = loadSelectedStudyDocumentIds();
        if (!persistedIds || persistedIds.length === 0) return;

        const hydrated = await hydrateDocumentIds(persistedIds);
        if (cancelled) return;

        if (hydrated.length > 0) {
          setSelectedDocuments(hydrated);
          const persistedActiveId = loadActiveDocumentId();
          const activeDoc = resolveActiveStudyDocument(hydrated, persistedActiveId);
          setDocument(activeDoc);

          if (activeDoc && activeDoc.status === "ready") {
            setContentLoading(true);
            const content = await loadCachedContent(activeDoc.id);
            if (!cancelled) {
              setCachedContent(content);
              setContentLoading(false);
            }
          }
        } else {
          // Previously selected documents no longer resolve.
          saveSelectedStudyDocumentIds([]);
          saveActiveDocumentId(null);
        }
      } finally {
        if (!cancelled) hasRestoredRef.current = true;
      }
    }

    restoreActiveStudySession();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keeps localStorage in sync with the live study selection and active document.
  useEffect(() => {
    if (!hasRestoredRef.current) return;
    saveSelectedStudyDocumentIds(selectedDocuments.map((doc) => doc.id), document?.id ?? null);
  }, [selectedDocuments, document]);

  function handleContentGenerated(kind, value) {
    setCachedContent((previous) => mergeGeneratedContent(previous, kind, value));
  }

  async function handleSelectActiveDocument(doc) {
    if (document?.id === doc?.id) return;
    setDocument(doc);
    setCachedContent(null);

    if (!doc) return;

    markDocumentOpened(doc.id)
      .catch(() => {})
      .finally(() => setRefreshSignal((count) => count + 1));

    if (doc.status !== "ready") return;
    setContentLoading(true);
    const content = await loadCachedContent(doc.id);
    setCachedContent(content);
    setContentLoading(false);
  }

  async function handleOpenDocument(doc) {
    setSelectionError(null);
    const res = openStudyDocument(selectedDocuments, doc, MAX_STUDY_DOCUMENTS);
    if (res.error) {
      setSelectionError(res.error);
    }
    setSelectedDocuments(res.nextDocuments);
    await handleSelectActiveDocument(res.activeDocument);
  }

  function handleToggleSelect(doc) {
    setSelectionError(null);
    const res = toggleStudyDocument(selectedDocuments, doc, MAX_STUDY_DOCUMENTS);
    if (res.error) {
      setSelectionError(res.error);
      return;
    }

    setSelectedDocuments(res.nextDocuments);

    // If the unselected document was active, focus the next available document
    if (document?.id === doc.id) {
      const nextActive = resolveActiveStudyDocument(res.nextDocuments, null);
      handleSelectActiveDocument(nextActive);
    } else if (!document && res.nextDocuments.length > 0) {
      handleSelectActiveDocument(res.nextDocuments[0]);
    }
  }

  function handleRemoveDocument(documentId) {
    setSelectionError(null);
    const res = removeStudyDocument(selectedDocuments, documentId);
    setSelectedDocuments(res.nextDocuments);

    if (document?.id === documentId) {
      const nextActive = resolveActiveStudyDocument(res.nextDocuments, null);
      handleSelectActiveDocument(nextActive);
    }
  }

  async function handleUploadComplete(newDocument) {
    setSelectionError(null);
    const res = syncStudyUpload(selectedDocuments, newDocument, MAX_STUDY_DOCUMENTS);
    setSelectedDocuments(res.nextDocuments);
    await handleSelectActiveDocument(res.activeDocument);
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setSelectedDocuments((previous) =>
      previous.map((doc) => (doc.id === documentId ? updated : doc))
    );
    setDocument((previous) => (previous && previous.id === documentId ? updated : previous));
    setRefreshSignal((count) => count + 1);
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    const remaining = selectedDocuments.filter((doc) => doc.id !== documentId);
    setSelectedDocuments(remaining);
    if (document && document.id === documentId) {
      const nextActive = resolveActiveStudyDocument(remaining, null);
      handleSelectActiveDocument(nextActive);
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
          selectedDocumentIds={selectedDocuments.map((doc) => doc.id)}
          selectable={true}
          selectionScope="study"
          maxSelected={MAX_STUDY_DOCUMENTS}
          onOpen={handleOpenDocument}
          onRename={handleRename}
          onDelete={handleDelete}
          onToggleSelect={handleToggleSelect}
          onUploadComplete={handleUploadComplete}
        />
      </aside>

      <main
        aria-label="Study workspace"
        className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-y-auto lg:p-10"
      >
        <StudyWorkspace
          document={document}
          selectedDocuments={selectedDocuments}
          contentLoading={contentLoading}
          cachedContent={cachedContent}
          onContentGenerated={handleContentGenerated}
          onSelectActiveDocument={handleSelectActiveDocument}
          onRemoveDocument={handleRemoveDocument}
          onOpenDocumentSelector={() => setIsPickerOpen(true)}
          selectionError={selectionError}
        />
      </main>

      {isPickerOpen && (
        <Modal
          title="Select documents to study"
          onClose={() => setIsPickerOpen(false)}
          maxWidthClassName="max-w-2xl"
        >
          <LibraryPanel
            refreshSignal={refreshSignal}
            activeDocumentId={document?.id ?? null}
            selectedDocumentIds={selectedDocuments.map((doc) => doc.id)}
            selectable={true}
            selectionScope="study"
            maxSelected={MAX_STUDY_DOCUMENTS}
            onOpen={(doc) => {
              handleOpenDocument(doc);
              setIsPickerOpen(false);
            }}
            onRename={handleRename}
            onDelete={handleDelete}
            onToggleSelect={handleToggleSelect}
            onUploadComplete={handleUploadComplete}
          />
        </Modal>
      )}
    </div>
  );
}

export default StudyPage;
