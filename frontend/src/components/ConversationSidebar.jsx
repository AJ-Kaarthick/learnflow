import { useRef, useState } from "react";

// Same delete-icon glyph DocumentList.jsx already uses for a document
// row, reused here for a conversation row so the two "delete this
// thing" affordances in the app look identical (V2.4 Milestone 2
// Phase 3 QA fix, issue 1).
function DeleteIcon({ busy = false }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={`h-3.5 w-3.5 ${busy ? "animate-pulse" : ""}`}
      aria-hidden="true"
    >
      <path
        d="M6 7h12M9.5 7V5.25A1.25 1.25 0 0110.75 4h2.5A1.25 1.25 0 0114.5 5.25V7m2.25 0-.62 12.13A1.75 1.75 0 0114.38 21H9.62a1.75 1.75 0 01-1.75-1.87L7.25 7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// The conversation list/sidebar for the Chat page (V2.4 Milestone 2,
// frontend) — the ChatGPT-like piece of this milestone's brief:
// "There is a conversation list/sidebar/area in the Chat workspace...
// the active conversation is clearly represented... clicking an
// existing conversation switches to it."
//
// Deliberately mostly-dumb: every conversation shown here, which one
// is active, and what "New" does are all owned by ChatPage.jsx — this
// component reports clicks back up via onSelect/onCreateNew/onRename,
// the same "container owns data, presentational component owns
// markup" split every other panel in this app already follows (see
// LibraryPanel/DocumentList). The one piece of state genuinely local
// to this component is which row (if any) is currently being renamed
// — see editingConversationId below — since that's transient UI state
// no other part of the app needs to know about, exactly like
// LibraryPanel's own rename-in-place flow for a document row.
//
// V2.4 Milestone 2 Phase 3: manual renaming (PATCH
// /conversations/{id}, via ChatPage's onRename) — AI-generated titles
// are still out of scope for this phase; the title shown for an
// unrenamed conversation is still exactly the backend's own default
// ("New Conversation" — see ConversationSummaryResponse.title in
// schemas/conversation.py).
function formatConversationTimestamp(isoString) {
  if (!isoString) return "";
  const then = new Date(isoString).getTime();
  if (Number.isNaN(then)) return "";

  const diffMs = Date.now() - then;
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  try {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(then));
  } catch {
    return "";
  }
}

function ConversationSidebar({
  conversations,
  activeConversationId,
  isLoading,
  isCreating,
  error,
  actionError,
  onSelect,
  onCreateNew,
  onRename,
  onDelete,
  onRetry,
}) {
  const [editingConversationId, setEditingConversationId] = useState(null);
  const [editingValue, setEditingValue] = useState("");
  // Mirrors DocumentList.jsx's own `busyId` for its delete button:
  // local, presentational-only state tracking which row's delete is
  // in flight, so that row (and only that row) can show a disabled/
  // pulsing icon while awaiting onDelete — not global loading state,
  // since deleting one conversation shouldn't visually block the rest
  // of an already-loaded list (V2.4 Milestone 2 Phase 3 QA fix, issue 1).
  const [deletingConversationId, setDeletingConversationId] = useState(null);
  // Unmounting a focused input (which cancelEditing's state update
  // does, by switching that row back to its non-editing branch) can,
  // depending on the browser, still fire a trailing native blur on
  // the way out — and this input's onBlur commits. Without this
  // guard, pressing Escape could occasionally still end up calling
  // onRename with whatever was typed, exactly the outcome Escape is
  // supposed to avoid. Set synchronously in the same keydown handler
  // that cancels, so it's already true by the time any such blur
  // reaches onBlur below, regardless of timing.
  const skipNextBlurCommitRef = useRef(false);

  function handleEditBlur(conversation) {
    if (skipNextBlurCommitRef.current) {
      skipNextBlurCommitRef.current = false;
      return;
    }
    commitEditing(conversation);
  }

  function startEditing(conversation) {
    setEditingConversationId(conversation.id);
    setEditingValue(conversation.title);
  }

  function cancelEditing() {
    setEditingConversationId(null);
    setEditingValue("");
  }

  // Blank or unchanged (after trimming) just cancels rather than
  // calling the API — matches the backend's own "title cannot be
  // blank" rule without needing a round trip to find that out, and an
  // unchanged title has nothing to persist.
  function commitEditing(conversation) {
    const trimmed = editingValue.trim();
    if (!trimmed || trimmed === conversation.title) {
      cancelEditing();
      return;
    }
    onRename(conversation.id, trimmed);
    cancelEditing();
  }

  // Same confirm-then-call-the-prop shape as DocumentList.jsx's own
  // handleDelete for a document row — a native confirm() is enough
  // friction for a destructive, unrecoverable action without a whole
  // custom modal, and keeps the two "delete" flows in this app
  // consistent with each other.
  async function handleDelete(conversation) {
    const confirmed = window.confirm(`Delete "${conversation.title}"? This can't be undone.`);
    if (!confirmed) return;

    setDeletingConversationId(conversation.id);
    try {
      await onDelete(conversation.id);
    } finally {
      setDeletingConversationId(null);
    }
  }

  return (
    <div className="flex h-full min-w-0 min-h-0 flex-col gap-3">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Conversations</h2>
        <button
          type="button"
          onClick={onCreateNew}
          disabled={isCreating}
          title="Start a new, independent conversation (Ctrl/Cmd+Shift+N)"
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
            <path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4Z" />
          </svg>
          {isCreating ? "Creating…" : "New"}
        </button>
      </div>

      {/* Distinct from the list-loading `error` state below (which
          replaces the whole list area) — this is a one-line, non-
          blocking notice for an action that failed (e.g. "New" or a
          rename couldn't reach the backend) while the existing list
          stays fully usable underneath it. */}
      {actionError && <p className="shrink-0 text-xs text-red-600">{actionError}</p>}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-slate-100 bg-surface">
        {isLoading ? (
          <p className="p-4 text-sm text-slate-500">Loading conversations...</p>
        ) : error ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center">
            <p className="text-sm font-medium text-slate-700">Couldn&apos;t load conversations</p>
            <p className="text-xs text-slate-400">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-1 text-xs font-medium text-accent-700 hover:text-accent-800"
            >
              Try again
            </button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1 p-4 text-center">
            <p className="text-sm font-medium text-slate-700">No conversations yet</p>
            <p className="text-xs text-slate-400">Start one to begin chatting.</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {conversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId;
              const isEditing = editingConversationId === conversation.id;

              return (
                <li key={conversation.id}>
                  {isEditing ? (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        commitEditing(conversation);
                      }}
                      className="px-3 py-2"
                    >
                      <input
                        autoFocus
                        type="text"
                        value={editingValue}
                        onChange={(event) => setEditingValue(event.target.value)}
                        onBlur={() => handleEditBlur(conversation)}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") {
                            event.preventDefault();
                            skipNextBlurCommitRef.current = true;
                            cancelEditing();
                          }
                        }}
                        maxLength={200}
                        aria-label="Conversation name"
                        className="w-full rounded border border-accent-400 bg-surface px-2 py-1 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                      />
                    </form>
                  ) : (
                    <div className={`group flex min-w-0 items-center ${isActive ? "bg-accent-50" : "hover:bg-slate-50"}`}>
                      <button
                        type="button"
                        onClick={() => onSelect(conversation.id)}
                        aria-current={isActive ? "true" : undefined}
                        className="min-w-0 flex-1 px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
                      >
                        <p
                          className={`truncate text-sm ${
                            isActive ? "font-semibold text-accent-800" : "font-medium text-slate-700"
                          }`}
                        >
                          {conversation.title}
                        </p>
                        <p className={`mt-0.5 text-xs ${isActive ? "text-accent-600" : "text-slate-400"}`}>
                          {formatConversationTimestamp(conversation.updated_at)}
                        </p>
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          // Renaming shouldn't also switch the active
                          // conversation — this button sits inside the
                          // same row as the select button above, so
                          // the click needs to stop there rather than
                          // bubble up to anything listening higher.
                          event.stopPropagation();
                          startEditing(conversation);
                        }}
                        aria-label={`Rename ${conversation.title}`}
                        title="Rename"
                        className="shrink-0 rounded p-1.5 text-slate-300 transition-colors hover:bg-slate-200 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                      >
                        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
                          <path d="M13.586 3.586a2 2 0 1 1 2.828 2.828l-.793.793-2.828-2.828.793-.793ZM11.379 5.793 3 14.172V17h2.828l8.38-8.379-2.83-2.828Z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          // Same reasoning as the rename button above:
                          // stop this from also selecting the row.
                          event.stopPropagation();
                          handleDelete(conversation);
                        }}
                        disabled={deletingConversationId === conversation.id}
                        aria-label={`Delete ${conversation.title}`}
                        title="Delete"
                        className="mr-2 shrink-0 rounded p-1.5 text-slate-300 transition-colors hover:bg-red-100 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <DeleteIcon busy={deletingConversationId === conversation.id} />
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default ConversationSidebar;
