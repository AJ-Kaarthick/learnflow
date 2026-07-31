import ChatPanel from "./ChatPanel";
import { getConversationKey } from "../utils/persistence";

// The right panel (≈26%) of the workspace: a persistent home for the
// AI assistant. `min-h-0` on the flex column plus `h-full` here (its
// parent <aside> in WorkspaceShell is a fixed-height, overflow-hidden
// box) is what lets ChatPanel's own message list scroll independently
// while its input stays pinned to the bottom — the "sticky chat"
// behavior — instead of the whole column scrolling as one unit.
function AssistantPanel({ selectedDocuments, onToggleSelect }) {
  return (
    <div className="flex h-full min-w-0 min-h-0 flex-col gap-4">
      <div className="shrink-0 space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">AI Assistant</h2>

        {selectedDocuments.length > 0 && (
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
                  className="shrink-0 rounded-full text-accent-400 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {selectedDocuments.length === 0 ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-slate-200 p-6 text-center">
          <p className="text-sm font-medium text-slate-700">No documents selected</p>
          <p className="max-w-[16rem] text-xs text-slate-400">
            Click a document in the library to start chatting with it, or check more than one to
            chat across several at once.
          </p>
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          {/* Keyed by the same sorted-document-ids logic ChatPanel
              uses for its storage key (getConversationKey), so
              switching to a different document combination always
              remounts into — and restores — the right conversation,
              never a stale one left over from the previous
              selection. */}
          <ChatPanel
            key={`chat-${getConversationKey(selectedDocuments.map((selected) => selected.id))}`}
            documents={selectedDocuments}
          />
        </div>
      )}
    </div>
  );
}

export default AssistantPanel;
