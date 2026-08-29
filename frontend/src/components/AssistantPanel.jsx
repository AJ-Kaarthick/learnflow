import { useState } from "react";
import ChatPanel from "./ChatPanel";
import LibraryPanel from "./LibraryPanel";
import Modal from "./Modal";

// A persistent home for the AI assistant within whichever page mounts
// it. `min-h-0` on the flex column plus `h-full` here (its parent
// element is a fixed-height, overflow-hidden box — ChatPage's main
// column, see ChatPage.jsx) is what lets ChatPanel's own message list
// scroll independently while its input stays pinned to the bottom —
// the "sticky chat" behavior — instead of the whole column scrolling
// as one unit.
//
// V2.4 Milestone 2 (frontend): this panel used to be keyed by a hash
// of the selected document ids (getConversationKey) — the old "one
// conversation per unique document combination" model, entirely
// local to the browser. It's now keyed by the active *conversation*'s
// own id instead, the actual backend entity ChatPage now manages (see
// api/conversations.js) — switching conversations (a new id) still
// correctly remounts ChatPanel into a fresh instance, but changing
// which documents are associated with the *same* conversation no
// longer does, matching the backend's own design intent (see
// replace_conversation_documents's docstring in
// routes_conversations.py: "this never changes the conversation's
// id ... which is the entire point of Milestone 2 over the old
// document-set-derived conversation key").
//
// V2.4 Milestone 2 Phase 3: this panel now also owns the "+"
// document-picker modal, replacing Chat's old permanent middle
// Library column. The modal's contents are just `LibraryPanel` itself
// — the exact same search/sort/select/rename/delete/upload component
// Study still uses as a full column (see StudyPage.jsx, entirely
// unaffected by this) — wrapped in `Modal` (the shared dialog shell
// every other in-app dialog already uses). No document-management
// logic was duplicated or reimplemented to build this: every handler
// below (onOpenDocument, onRenameDocument, onDeleteDocument,
// onUploadComplete, onToggleSelect) is the same function ChatPage
// always owned, just wired to LibraryPanel one level down from where
// it used to be. In particular, onUploadComplete is still exactly
// ChatPage's handleUploadComplete, which still goes through
// UploadForm's own call to the global POST /documents endpoint (see
// api/documents.js's uploadDocument) — a document uploaded from this
// picker is a normal, global document from the instant it's created,
// visible to Study and to every other conversation's picker too,
// never a Chat-only or conversation-scoped upload.
function AssistantPanel({
  conversation,
  isConversationLoading,
  conversationError,
  onRetryLoadConversation,
  selectedDocuments,
  onToggleSelect,
  onMessageSent,
  refreshSignal,
  onOpenDocument,
  onRenameDocument,
  onDeleteDocument,
  onUploadComplete,
}) {
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  return (
    <div className="flex h-full min-w-0 min-h-0 flex-col gap-4">
      <div className="shrink-0 space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">AI Assistant</h2>

        <div className="flex flex-wrap items-center gap-1.5">
          {selectedDocuments.map((selected) => (
            <span
              key={selected.id}
              className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-accent-50 py-1 pl-3 pr-2 text-xs font-medium text-accent-800"
            >
              <span className="truncate">{selected.original_filename}</span>
              <button
                type="button"
                onClick={() => onToggleSelect(selected)}
                aria-label={`Remove ${selected.original_filename} from chat`}
                className="shrink-0 rounded-full text-accent-400 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                &times;
              </button>
            </span>
          ))}

          {/* The one always-visible entry point to document selection
              now that there's no permanent library column — present
              whether 0 or several documents are already selected, so
              it's equally the "get started" action and the "add
              another document" action. */}
          <button
            type="button"
            onClick={() => setIsPickerOpen(true)}
            className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:border-accent-400 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
              <path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4Z" />
            </svg>
            {selectedDocuments.length === 0 ? "Add documents" : "Add"}
          </button>
        </div>
      </div>

      {isConversationLoading || !conversation ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-slate-200 p-6 text-center">
          {conversationError ? (
            <>
              <p className="text-sm font-medium text-slate-700">Couldn&apos;t load this conversation</p>
              <p className="max-w-[16rem] text-xs text-slate-400">{conversationError}</p>
              <button
                type="button"
                onClick={onRetryLoadConversation}
                className="mt-2 text-xs font-medium text-accent-700 hover:text-accent-800"
              >
                Try again
              </button>
            </>
          ) : (
            <p className="text-sm text-slate-500">Loading conversation...</p>
          )}
        </div>
      ) : selectedDocuments.length === 0 ? (
        // V2.4 Milestone 2 Phase 3: reworded from "No documents
        // selected" (which read like an error/broken state) to an
        // actionable next step, and the button below opens the exact
        // same picker as the chip row's own "Add documents" control —
        // this is a second, more prominent entry point to it for a
        // conversation that has nothing selected yet, not a separate
        // flow.
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-200 p-6 text-center">
          <p className="text-sm font-medium text-slate-700">Start a conversation</p>
          <p className="max-w-[16rem] text-xs text-slate-400">Select a document to begin chatting.</p>
          <button
            type="button"
            onClick={() => setIsPickerOpen(true)}
            className="mt-2 rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            Select documents
          </button>
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          <ChatPanel
            key={conversation.id}
            conversationId={conversation.id}
            initialMessages={conversation.messages}
            documents={selectedDocuments}
            onMessageSent={onMessageSent}
          />
        </div>
      )}

      {isPickerOpen && (
        <Modal title="Select documents" onClose={() => setIsPickerOpen(false)} maxWidthClassName="max-w-2xl">
          <LibraryPanel
            refreshSignal={refreshSignal}
            activeDocumentId={selectedDocuments.length === 1 ? selectedDocuments[0].id : null}
            selectedDocumentIds={selectedDocuments.map((selected) => selected.id)}
            onOpen={onOpenDocument}
            onRename={onRenameDocument}
            onDelete={onDeleteDocument}
            onToggleSelect={onToggleSelect}
            onUploadComplete={onUploadComplete}
          />
        </Modal>
      )}
    </div>
  );
}

export default AssistantPanel;
