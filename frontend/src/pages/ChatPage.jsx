import { useEffect, useRef, useState } from "react";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import AssistantPanel from "../components/AssistantPanel";
import LibraryPanel from "../components/LibraryPanel";
import { toDocumentChip as toChip } from "../utils/documentChip";
import { hydrateDocumentIds } from "../utils/documentHydration";
import { resolveChatUploadSync } from "../utils/documentUploadSync";
import { loadSelectedDocumentIds, saveSelectedDocumentIds } from "../utils/persistence";

// V2.4 Milestone 1 UX polish (issue 2): the chip-building logic that
// used to live here (a private, un-exported `toChip`) now lives in
// utils/documentChip.js instead, specifically so it's unit-testable
// on its own — see that module's docstring for why that mattered in
// practice. `toChip` stays as the local name every call site below
// already uses.

// V2.4 Milestone 1: AI Chat as its own page, carved out of the old
// combined workspace's right-hand panel. Reuses the exact same
// AssistantPanel -> ChatPanel components that used to live in that
// narrow sidebar — they were already layout-agnostic (no hardcoded
// width, just `h-full`/flex), so giving Chat "substantially more
// room" than before was purely a matter of the *page* layout below,
// not a change to the chat components themselves. No chat/retrieval
// logic is duplicated here: this page only owns which document(s)
// the conversation is grounded in, the same `selectedDocumentIds`
// piece of workspace state the old combined page already persisted
// separately from the active study document (see StudyPage for its
// half).
function ChatPage() {
  // Bumped whenever an action outside LibraryPanel's own search/sort
  // controls changes the underlying document data (select, rename,
  // delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  // Documents currently included in this conversation. Holds
  // {id, original_filename, status, character_count} — a trimmed copy
  // of each selected DocumentResponse (see toChip / toDocumentChip in
  // utils/documentChip.js), not bare ids — so AssistantPanel can show
  // readable chips *and* ChatPanel can tell a readable document from
  // an unreadable one (see documentReadiness.hasNoReadableText)
  // without either of them needing LibraryPanel to expose its whole
  // fetched list.
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  const hasRestoredRef = useRef(false);

  // Restores the previous session's selected chat documents on first
  // mount. Drops any id that no longer resolves (deleted in a
  // previous session, or from the Study page) both from what gets
  // restored and from what stays in storage, so a stale id doesn't
  // linger forever.
  useEffect(() => {
    let cancelled = false;

    async function restoreSelection() {
      try {
        const persistedIds = loadSelectedDocumentIds();
        if (!persistedIds || persistedIds.length === 0) return;

        const found = await hydrateDocumentIds(persistedIds);
        if (cancelled) return;

        // hydrateDocumentIds doesn't guarantee order — restore in the
        // originally-saved order so the chip row doesn't reshuffle
        // between sessions.
        const foundById = new Map(found.map((doc) => [doc.id, doc]));
        const restored = persistedIds.filter((id) => foundById.has(id)).map((id) => toChip(foundById.get(id)));

        setSelectedDocuments(restored);
        if (restored.length !== persistedIds.length) {
          saveSelectedDocumentIds(restored.map((doc) => doc.id));
        }
      } finally {
        if (!cancelled) hasRestoredRef.current = true;
      }
    }

    restoreSelection();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!hasRestoredRef.current) return;
    saveSelectedDocumentIds(selectedDocuments.map((selected) => selected.id));
  }, [selectedDocuments]);

  function handleToggleSelect(doc) {
    setSelectedDocuments((previous) => {
      const isSelected = previous.some((selected) => selected.id === doc.id);
      if (isSelected) {
        return previous.filter((selected) => selected.id !== doc.id);
      }
      return [...previous, toChip(doc)];
    });
  }

  // Clicking a document (rather than checking its box) makes it the
  // sole chat document, same "click = single, checkbox = add another"
  // behavior the combined workspace used for its automatic
  // single-document chat sync — just scoped entirely to this page's
  // own selection now, with no study document to also keep in sync.
  //
  // "Multi-document mode" isn't a separate flag — it's derived from
  // selectedDocuments itself: 0 or 1 selected is "single/automatic"
  // mode, where clicking a document keeps replacing the selection;
  // 2+ selected (only reachable by manually checking a second box) is
  // "multi-document mode", where the selection is entirely explicit
  // and clicking a document to peek at it must NOT silently derail an
  // in-progress multi-document conversation.
  function handleOpenForChat(doc) {
    setSelectedDocuments((previous) => (previous.length <= 1 ? [toChip(doc)] : previous));

    // Timestamp the open server-side (powers the "Recently Opened"
    // sort, and Home's "Continue studying" list) and refresh the
    // library so it reflects the new order. Best-effort: if this
    // fails, selecting the document for chat should still work.
    markDocumentOpened(doc.id)
      .catch(() => {})
      .finally(() => setRefreshSignal((count) => count + 1));
  }

  function handleUploadComplete(newDocument) {
    // The selection-merge rule lives in resolveChatUploadSync
    // (utils/documentUploadSync.js) — see that module's docstring for
    // the bug this fixes. Its `shouldRefreshLibrary` is always true
    // (a completed upload always changes the underlying document
    // list), which is why the refreshSignal bump below is
    // unconditional rather than gated on that flag: gating a setState
    // call on a value computed inside another setState's updater
    // would make it a side effect of that updater, which React may
    // invoke more than once (e.g. under StrictMode).
    setSelectedDocuments((previous) => resolveChatUploadSync(previous, newDocument).selectedDocuments);
    setRefreshSignal((count) => count + 1);
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setSelectedDocuments((previous) =>
      previous.map((selected) => (selected.id === documentId ? toChip(updated) : selected))
    );
    setRefreshSignal((count) => count + 1);
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    setSelectedDocuments((previous) => previous.filter((selected) => selected.id !== documentId));
    setRefreshSignal((count) => count + 1);
  }

  return (
    <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
      <aside
        aria-label="Document library"
        className="min-w-0 shrink-0 border-b border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[22%] lg:min-w-[260px] lg:max-w-[360px] lg:overflow-hidden lg:border-b-0 lg:border-r lg:p-6"
      >
        <LibraryPanel
          refreshSignal={refreshSignal}
          activeDocumentId={selectedDocuments.length === 1 ? selectedDocuments[0].id : null}
          selectedDocumentIds={selectedDocuments.map((selected) => selected.id)}
          onOpen={handleOpenForChat}
          onRename={handleRename}
          onDelete={handleDelete}
          onToggleSelect={handleToggleSelect}
          onUploadComplete={handleUploadComplete}
        />
      </aside>

      {/* The chat column used to be a fixed ~26%-wide sidebar (see
          the old WorkspaceShell/AssistantPanel) squeezed next to a
          three-panel workspace. It's the majority of the page now —
          AssistantPanel and ChatPanel needed no changes to grow into
          it, only this page's layout does. */}
      <main
        aria-label="AI chat"
        className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-hidden lg:p-8"
      >
        <AssistantPanel selectedDocuments={selectedDocuments} onToggleSelect={handleToggleSelect} />
      </main>
    </div>
  );
}

export default ChatPage;
