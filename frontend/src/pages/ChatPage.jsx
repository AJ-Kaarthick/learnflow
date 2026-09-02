import { useEffect, useRef, useState } from "react";
import { createConversation, deleteConversation, getConversation, listConversations, renameConversation, replaceConversationDocuments } from "../api/conversations";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import AssistantPanel from "../components/AssistantPanel";
import ConversationSidebar from "../components/ConversationSidebar";
import { orderHydratedDocuments } from "../utils/conversationDocuments";
import {
  applyGeneratedTitle,
  removeConversationFromList,
  renameConversationInList,
  resolveActiveConversationId,
  touchConversation,
  withNewConversation,
} from "../utils/conversationSelection";
import { toDocumentChip as toChip } from "../utils/documentChip";
import { hydrateDocumentIds } from "../utils/documentHydration";
import { resolveChatUploadSync } from "../utils/documentUploadSync";
import { loadActiveConversationId, saveActiveConversationId } from "../utils/persistence";
import { NEW_CONVERSATION_EVENT } from "../utils/shortcutEvents";

// V2.4 Milestone 1 UX polish (issue 2): the chip-building logic that
// used to live here (a private, un-exported `toChip`) now lives in
// utils/documentChip.js instead, specifically so it's unit-testable
// on its own — see that module's docstring for why that mattered in
// practice. `toChip` stays as the local name every call site below
// already uses.

// V2.4 Milestone 1: AI Chat as its own page, carved out of the old
// combined workspace's right-hand panel.
//
// V2.4 Milestone 2 (frontend): this page's job changed from "own which
// document(s) the one implicit chat session is grounded in" to "own
// the Chat workspace's whole conversation lifecycle" — the
// conversation list, which one is active, and (still) which documents
// the active conversation is grounded in, now as a property of that
// conversation rather than free-floating page state. The backend is
// the source of truth for everything about a conversation (see
// api/conversations.js and the ARCHITECTURE REQUIREMENTS in this
// milestone's brief); this page only ever persists *which* conversation
// was active (see utils/persistence.js's loadActiveConversationId),
// never its messages or documents — both of which a GET
// /conversations/{id} already restores in full.
//
// V2.4 Milestone 2 Phase 3: the page is Conversations | AI Chat now,
// not Conversations | Document Library | AI Chat — the permanent
// middle library column is gone. Document selection still goes
// through the exact same handlers this page always owned
// (handleOpenForChat, handleToggleSelect, handleRename, handleDelete,
// handleUploadComplete below); they're just handed to AssistantPanel
// now instead of directly to a `<LibraryPanel>` here, since
// AssistantPanel is what renders the library inside a picker modal —
// see AssistantPanel.jsx's own docstring for why that's a relocation,
// not a rewrite, of the same document-management logic.
function ChatPage() {
  // Bumped whenever an action outside the document picker's own
  // search/sort controls changes the underlying document data
  // (select, rename, delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  // The sidebar's list (ConversationSummaryResponse[] — id, title,
  // title_is_custom, created_at, updated_at; no documents/messages,
  // see GET /conversations). Ordered most-recently-active first by
  // the backend; withNewConversation/touchConversation
  // (utils/conversationSelection.js) preserve that ordering locally
  // for the two things that change it (creating one, sending a
  // message) without a full re-fetch.
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState(null);

  // The active conversation's full detail (metadata + documents +
  // messages — ConversationDetailResponse). `null` while nothing has
  // loaded yet (first mount, or mid-switch).
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [activeConversation, setActiveConversation] = useState(null);
  const [activeConversationLoading, setActiveConversationLoading] = useState(true);
  const [activeConversationError, setActiveConversationError] = useState(null);

  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  // A one-line, non-blocking notice for "New" failing — see
  // ConversationSidebar's actionError prop.
  const [conversationActionError, setConversationActionError] = useState(null);

  // The active conversation's documents, hydrated into the full
  // DocumentResponse shape (id, original_filename, status,
  // character_count, ...) and trimmed into chips (toChip) — the same
  // object shape AssistantPanel's chip row and ChatPanel's readiness
  // checks (splitDocumentsByReadability) have always taken. Sourced
  // from the active conversation's own associations now (see
  // hydrateActiveConversationDocuments below) rather than a page-level
  // selection restored from localStorage.
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  // Guards against a switch-in-flight response landing after a *later*
  // switch has already started — e.g. clicking conversation B while A's
  // detail fetch is still pending. Whichever load was the most recently
  // requested wins; a request whose id no longer matches this ref when
  // it resolves is discarded. This is the concrete mechanism behind
  // "protection against state from conversation A leaking into
  // conversation B" for the loading itself (see
  // utils/conversationMessages.js/conversationDocuments.js for the
  // equivalent guarantee on the pure mapping side).
  const latestRequestedConversationIdRef = useRef(null);

  // Guards the one-time initial-load effect below against React 18
  // StrictMode's dev-only double-invoke (mount -> cleanup -> mount
  // again, same component instance — see main.jsx). Every other
  // restore-on-mount effect in this app (see StudyPage's
  // restoreActiveDocument) is read-only, so running it twice is
  // harmless; this one can *create* a conversation for a genuinely
  // new user with none yet (see handleCreateConversation below), and
  // two independent invocations racing the same "the list is empty"
  // check could otherwise each decide to create one, leaving a stray
  // second empty conversation behind. A ref (not state) specifically
  // because it must already be set by the time the second invoke
  // happens — before either invocation's own async work has had a
  // chance to resolve — which only a synchronous, effect-scoped guard
  // like this can guarantee.
  const hasInitializedRef = useRef(false);

  // `forConversationId` is re-checked against
  // latestRequestedConversationIdRef *after* the (potentially slow —
  // one GET /documents/{id} per associated document) hydration below,
  // not just before starting it — a switch to a different conversation
  // that happens mid-hydration must not have this call's now-stale
  // result land on top of it once it finishes.
  async function hydrateActiveConversationDocuments(documentSummaries, forConversationId) {
    if (!documentSummaries || documentSummaries.length === 0) {
      if (latestRequestedConversationIdRef.current === forConversationId) setSelectedDocuments([]);
      return;
    }
    const hydrated = await hydrateDocumentIds(documentSummaries.map((summary) => summary.id));
    if (latestRequestedConversationIdRef.current !== forConversationId) return;
    setSelectedDocuments(orderHydratedDocuments(documentSummaries, hydrated).map(toChip));
  }

  // Fetches one conversation's full detail and makes it the active
  // one — shared by the initial-load flow, clicking a conversation in
  // the sidebar, and (indirectly) creating a new one.
  async function loadConversationDetail(conversationId) {
    latestRequestedConversationIdRef.current = conversationId;
    setActiveConversationId(conversationId);
    setActiveConversationLoading(true);
    setActiveConversationError(null);
    // Cleared immediately (synchronously with the switch), not just
    // after the new conversation's documents finish hydrating below —
    // otherwise the chip row above (rendered unconditionally in
    // AssistantPanel, regardless of loading state) would briefly keep
    // showing the *previous* conversation's document chips while this
    // one is still loading. A visible instance of the same leakage
    // the pure mapping functions guard against internally.
    setSelectedDocuments([]);

    try {
      const detail = await getConversation(conversationId);
      if (latestRequestedConversationIdRef.current !== conversationId) return; // superseded by a later switch

      setActiveConversation(detail);
      saveActiveConversationId(conversationId);
      await hydrateActiveConversationDocuments(detail.documents, conversationId);
    } catch (error) {
      if (latestRequestedConversationIdRef.current !== conversationId) return;
      setActiveConversation(null);
      setActiveConversationError(error.message);
    } finally {
      if (latestRequestedConversationIdRef.current === conversationId) {
        setActiveConversationLoading(false);
      }
    }
  }

  // Loads the conversation list once on mount, determines which
  // conversation should be active (resolveActiveConversationId —
  // restoring the last-active one if it still exists, otherwise the
  // most recent conversation), and — only for a genuinely first-time
  // user with no conversations at all — creates one so Chat opens
  // ready to use rather than to an empty sidebar with nothing to
  // click.
  //
  // Phase 3 fix: this used to also track a per-invocation `cancelled`
  // flag, set in the effect's cleanup, and check it before applying
  // `listConversations()`'s result. That interacted badly with
  // `hasInitializedRef` above: StrictMode's cleanup-after-first-setup
  // still ran (and set `cancelled = true`) even though
  // `hasInitializedRef` was specifically what made the *second*
  // setup a no-op — so the one real `initialize()` call had its own
  // result silently discarded by a cleanup that was meant to guard
  // against a second invocation, not against itself. The sidebar
  // stayed on "Loading conversations..." forever, and — since the
  // "no conversations yet" branch below never ran either — a fresh
  // install with zero conversations never got its first one created.
  // `hasInitializedRef` alone already guarantees `initialize()` runs
  // exactly once (the second `useEffect` invocation returns before
  // ever calling it), so there's nothing left for a cancellation flag
  // to protect against here.
  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;

    async function initialize() {
      setConversationsLoading(true);
      setConversationsError(null);
      try {
        const list = await listConversations();
        setConversations(list);
        setConversationsLoading(false);

        const persistedId = loadActiveConversationId();
        const resolvedId = resolveActiveConversationId(list, persistedId);

        if (resolvedId) {
          await loadConversationDetail(resolvedId);
        } else {
          await handleCreateConversation();
        }
      } catch (error) {
        setConversationsError(error.message);
        setConversationsLoading(false);
        setActiveConversationLoading(false);
      }
    }

    initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSelectConversation(conversationId) {
    if (conversationId === activeConversationId) return;
    loadConversationDetail(conversationId);
  }

  // Creates a genuinely new, independent conversation — the frontend
  // half of this milestone's core requirement. Deliberately starts
  // with no associated documents (rather than inheriting whatever was
  // selected in the conversation being left): see the milestone
  // brief's own example ("New Conversation → Conversation B →
  // documents C" — a distinct document set, not a carried-over one).
  // Never touches `conversations`' existing entries or the previous
  // active conversation's data at all — withNewConversation only ever
  // adds, and the previous conversation's own row in the database is
  // never written to by this call.
  async function handleCreateConversation() {
    setIsCreatingConversation(true);
    setConversationActionError(null);
    try {
      const created = await createConversation([]);
      setConversations((previous) => withNewConversation(previous, created));
      latestRequestedConversationIdRef.current = created.id;
      setActiveConversationId(created.id);
      setActiveConversation(created);
      setActiveConversationError(null);
      setActiveConversationLoading(false);
      setSelectedDocuments([]);
      saveActiveConversationId(created.id);
    } catch (error) {
      setConversationActionError(`Couldn't start a new conversation. ${error.message}`);
    } finally {
      setIsCreatingConversation(false);
    }
  }

  // Manual conversation renaming (Milestone 2 Phase 3) — PATCH
  // /conversations/{id}. Updates this page's own copies of the
  // conversation's title (the sidebar's list entry, and — if it's the
  // active one — activeConversation itself, so AssistantPanel/
  // ChatPanel would see the new title too if they ever displayed it)
  // from the backend's own response rather than echoing back
  // `newTitle` directly, so trimming/normalization the backend applies
  // is reflected here too. Deliberately does not reorder the sidebar
  // list — see renameConversationInList's docstring
  // (utils/conversationSelection.js) for why a rename isn't an
  // "activity" event the way sending a message is.
  async function handleRenameConversation(conversationId, newTitle) {
    setConversationActionError(null);
    try {
      const updated = await renameConversation(conversationId, newTitle);
      setConversations((previous) => renameConversationInList(previous, conversationId, updated.title));
      setActiveConversation((previous) =>
        previous && previous.id === conversationId
          ? { ...previous, title: updated.title, title_is_custom: updated.title_is_custom }
          : previous
      );
    } catch (error) {
      setConversationActionError(`Couldn't rename this conversation. ${error.message}`);
    }
  }

  // Deletes a conversation (V2.4 Milestone 2 Phase 3 QA fix, issue 1)
  // -- DELETE /conversations/{id}. The backend route itself already
  // existed and was already fully tested (see
  // backend/tests/test_conversations.py's deletion tests); this is
  // the frontend wiring that was missing. Errors surface the same way
  // a failed rename does (setConversationActionError, no rethrow) --
  // ConversationSidebar's own handleDelete just awaits this to know
  // when to clear its per-row busy indicator, whether it succeeded or
  // not.
  //
  // What happens to the *active* conversation after a delete depends
  // on whether the deleted one was it:
  //   - Not the active one: only the sidebar list changes.
  //   - The active one, with other conversations remaining: switches
  //     to the most-recently-active of what's left, the exact same
  //     "persisted id no longer resolves" fallback
  //     resolveActiveConversationId already uses when a persisted id
  //     from a previous session is gone (e.g. deleted in another tab).
  //   - The active one, and it was the *last* conversation: reuses
  //     the exact same bootstrap this page already runs for a
  //     genuinely first-time user with zero conversations (see the
  //     initial-load effect's own handleCreateConversation() call)
  //     rather than inventing a second "zero conversations" UI state
  //     — matching the brief's "handle deleting the last conversation
  //     according to the existing conversation lifecycle/design."
  async function handleDeleteConversation(conversationId) {
    setConversationActionError(null);
    const wasActive = conversationId === activeConversationId;

    try {
      await deleteConversation(conversationId);
    } catch (error) {
      setConversationActionError(`Couldn't delete this conversation. ${error.message}`);
      return;
    }

    // `remaining` here (used only to decide what happens to the
    // *active* conversation below) is computed from this render's own
    // `conversations` closure; the actual list state update just
    // above uses the functional updater form instead, the same
    // race-safety reasoning setConversations already uses in
    // handleRenameConversation, so two deletions resolving out of
    // order can't have the second one silently resurrect the first.
    const remaining = removeConversationFromList(conversations, conversationId);
    setConversations((previous) => removeConversationFromList(previous, conversationId));

    if (!wasActive) return;

    if (remaining.length === 0) {
      await handleCreateConversation();
      return;
    }

    const nextActiveId = resolveActiveConversationId(remaining, null);
    await loadConversationDetail(nextActiveId);
  }

  // Ctrl/Cmd+Shift+N (Milestone 4) is caught globally in AppShell and
  // relayed here via a CustomEvent (see utils/shortcutEvents.js).
  // Previously this cleared the current document combination's local
  // history; now that "new conversation" is a real backend entity, it
  // triggers the exact same flow as clicking "New" in the sidebar.
  useEffect(() => {
    function handleShortcut() {
      if (!isCreatingConversation) handleCreateConversation();
    }
    window.addEventListener(NEW_CONVERSATION_EVENT, handleShortcut);
    return () => window.removeEventListener(NEW_CONVERSATION_EVENT, handleShortcut);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCreatingConversation]);

  // Persists the active conversation's document association
  // (PUT /conversations/{id}/documents) after an optimistic local
  // update, so the chip row feels instant while staying backed by the
  // same server-side association GET /conversations/{id} restores.
  // Reverts the optimistic change (and logs, for debugging — this
  // mirrors how document toggling had no error handling at all before
  // Milestone 2, since it was pure local state with nothing to fail;
  // now that it's a network call, silently keeping an association the
  // server never actually saved would be worse than reverting) if the
  // request fails.
  async function syncSelectedDocuments(nextSelectedDocuments) {
    const previous = selectedDocuments;
    setSelectedDocuments(nextSelectedDocuments);

    if (!activeConversationId) return;
    try {
      await replaceConversationDocuments(activeConversationId, nextSelectedDocuments.map((doc) => doc.id));
    } catch (error) {
      setSelectedDocuments(previous);
      // eslint-disable-next-line no-console
      console.error("Couldn't update this conversation's documents:", error);
    }
  }

  function handleToggleSelect(doc) {
    const isSelected = selectedDocuments.some((selected) => selected.id === doc.id);
    const next = isSelected
      ? selectedDocuments.filter((selected) => selected.id !== doc.id)
      : [...selectedDocuments, toChip(doc)];
    syncSelectedDocuments(next);
  }

  // Clicking a document (rather than checking its box) makes it the
  // sole chat document for the active conversation, same "click =
  // single, checkbox = add another" behavior as before — just synced
  // to the backend now instead of only updating local state.
  //
  // "Multi-document mode" isn't a separate flag — it's derived from
  // selectedDocuments itself: 0 or 1 selected is "single/automatic"
  // mode, where clicking a document keeps replacing the selection;
  // 2+ selected (only reachable by manually checking a second box) is
  // "multi-document mode", where the selection is entirely explicit
  // and clicking a document to peek at it must NOT silently derail an
  // in-progress multi-document conversation.
  function handleOpenForChat(doc) {
    if (selectedDocuments.length <= 1) {
      syncSelectedDocuments([toChip(doc)]);
    }

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
    // the bug this fixes. Computed directly off the current
    // `selectedDocuments` (rather than via a setState updater) since
    // this now also needs to feed the resulting list into
    // syncSelectedDocuments' own network call, not just a second
    // setState call.
    const { selectedDocuments: next } = resolveChatUploadSync(selectedDocuments, newDocument);
    syncSelectedDocuments(next);
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
    // No PUT /conversations/{id}/documents call needed here —
    // delete_document (routes_documents.py) already cleans up this
    // document's ConversationDocument rows server-side, for every
    // conversation it was associated with, not just the active one.
    // This only needs to keep the active conversation's own chip row
    // in sync with that.
    setSelectedDocuments((previous) => previous.filter((selected) => selected.id !== documentId));
    setRefreshSignal((count) => count + 1);
  }

  // Mirrors the backend's own "sending a message bumps
  // Conversation.updated_at" behavior (see send_message's docstring
  // in routes_conversations.py) in the sidebar's local list, so the
  // conversation just messaged jumps to the top the same way it would
  // after a fresh GET /conversations — without actually issuing one.
  //
  // Also folds the newly persisted turn (`response.user_message` /
  // `response.assistant_message`, both already in the backend's own
  // MessageResponse shape) into this page's cached
  // `activeConversation.messages` — otherwise that cache is only ever
  // set once, when the conversation is first loaded (see
  // loadConversationDetail above), and would go stale the moment a
  // message is sent. That staleness would normally be invisible
  // (ChatPanel owns its own message state after mounting, and never
  // re-reads this cache on its own) — until AssistantPanel's layout
  // unmounts and remounts ChatPanel, which happens whenever the
  // document chip row goes from 0 to 1+ chips within the *same*
  // conversation (see AssistantPanel.jsx's three-way branch): a
  // remount re-initializes `messages` from exactly this cache, so an
  // out-of-date one would make a just-sent turn appear to vanish.
  //
  // V2.4 Milestone 2 Phase 4 (automatic conversation naming): when
  // this send also generated a new title (see
  // ConversationMessageResponse.generated_title in
  // schemas/conversation.py — non-null only on the exact request
  // where the backend both generated *and* persisted one), applies it
  // to the sidebar's local list the same way handleRenameConversation
  // already does for a manual rename, and to `activeConversation`
  // itself so a title shown anywhere else in the Chat workspace stays
  // in sync too — all without a page refresh or a follow-up GET,
  // satisfying this phase's "update the sidebar immediately" and
  // "manual renaming must continue to work independently" requirements
  // in one pass. A null `generated_title` (the overwhelmingly common
  // case — every message after a conversation's first, and every
  // first message where generation didn't happen or lost the
  // race-protection check server-side) is a no-op here, same as
  // applyGeneratedTitle's own no-op-on-no-match reasoning.
  function handleMessageSent(sentConversationId, response) {
    setConversations((previous) => touchConversation(previous, sentConversationId, new Date().toISOString()));
    if (response?.generated_title) {
      setConversations((previous) => applyGeneratedTitle(previous, sentConversationId, response.generated_title));
    }
    setActiveConversation((previous) => {
      if (!previous || previous.id !== sentConversationId || !response) return previous;
      const withNewMessages = {
        ...previous,
        messages: [...previous.messages, response.user_message, response.assistant_message],
      };
      return response.generated_title
        ? { ...withNewMessages, title: response.generated_title }
        : withNewMessages;
    });
  }

  return (
    <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
      <aside
        aria-label="Conversations"
        className="min-w-0 shrink-0 border-b border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[20%] lg:min-w-[220px] lg:max-w-[300px] lg:overflow-hidden lg:border-b-0 lg:border-r lg:p-6"
      >
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          isLoading={conversationsLoading}
          isCreating={isCreatingConversation}
          error={conversationsError}
          actionError={conversationActionError}
          onSelect={handleSelectConversation}
          onCreateNew={handleCreateConversation}
          onRename={handleRenameConversation}
          onDelete={handleDeleteConversation}
          onRetry={() => window.location.reload()}
        />
      </aside>

      {/* V2.4 Milestone 2 Phase 3: this used to be Conversations |
          Document Library | AI Chat — a permanent middle column just
          for picking documents. That's gone; AI Chat is now the
          majority of the page, and document selection/upload happens
          through a "+" control inside AssistantPanel that opens the
          same document-management UI (LibraryPanel) in a modal
          instead of a fixed column — see AssistantPanel.jsx. Every
          handler passed down here is the exact same one this page
          always owned; only where it's rendered changed. */}
      <main aria-label="AI chat" className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-hidden lg:p-8">
        <AssistantPanel
          conversation={activeConversation}
          isConversationLoading={activeConversationLoading}
          conversationError={activeConversationError}
          onRetryLoadConversation={() => activeConversationId && loadConversationDetail(activeConversationId)}
          selectedDocuments={selectedDocuments}
          onToggleSelect={handleToggleSelect}
          onMessageSent={handleMessageSent}
          refreshSignal={refreshSignal}
          onOpenDocument={handleOpenForChat}
          onRenameDocument={handleRename}
          onDeleteDocument={handleDelete}
          onUploadComplete={handleUploadComplete}
        />
      </main>
    </div>
  );
}

export default ChatPage;
