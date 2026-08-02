import { useEffect, useState } from "react";
import AssistantPanel from "./AssistantPanel";
import LibraryPanel from "./LibraryPanel";
import ShortcutsDialog from "./ShortcutsDialog";
import StudyWorkspace from "./StudyWorkspace";
import TopBar from "./TopBar";
import { FOCUS_SEARCH_EVENT, NEW_CONVERSATION_EVENT, emitShortcutEvent } from "../utils/shortcutEvents";

// Form fields where a bare letter/slash keystroke is normal typing,
// not a shortcut attempt — the global listener below ignores its
// shortcuts entirely while one of these is focused (Milestone 4:
// "keyboard shortcuts must never interfere with normal typing").
// Ctrl/Cmd+Enter is the one exception, and it isn't handled here at
// all — it's a local keydown handler on the chat input itself (see
// ChatPanel), since that input *is* the intended target for it.
const TEXT_ENTRY_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

// The V2.1 workspace layout: a persistent top bar over a three-column
// desktop workspace (Library ≈20% / Study Workspace ≈60% / AI
// Assistant ≈20%). Columns are still fixed-width (not resizable —
// that's still a later milestone), but this pass fixes two things
// Milestone 1 got wrong:
//
// 1. Spacing. Milestone 1 nested three bordered, shadowed "cards"
//    inside a padded page, which read as a compressed dashboard
//    rather than a workspace. This version uses one continuous
//    surface split by subtle dividers (border only, no shadow, no
//    per-panel rounding) — the same visual language VS Code, Notion,
//    and Cursor use — with meaningfully larger padding and gaps.
//
// 2. Height. Milestone 1 used `min-h-screen`, which let the page grow
//    taller than the viewport whenever content did, which is what
//    let a chat response scroll the *browser window* (see ChatPanel's
//    old scrollIntoView call — removed) instead of just its own
//    column. This version locks the shell to exactly `h-screen` with
//    `overflow-hidden`, so there is no page-level scroll to hijack at
//    all on desktop — each column manages its own internal scroll.
//    Below `lg`, the columns stack and the page scrolls normally,
//    same as before; the viewport-locked behavior is a desktop-only
//    guarantee, consistent with this app being desktop-first.
//
// Milestone 4 adds one global keydown listener here — the single
// component mounted for the app's entire lifetime — for the handful
// of shortcuts that aren't naturally scoped to whichever input already
// has focus (see ChatPanel's own Ctrl/Cmd+Enter handler for the one
// that is). Two of the three dispatch a CustomEvent rather than
// calling into a child directly, since the component that owns the
// relevant action (LibraryPanel's search input, ChatPanel's
// conversation) is several layers down and may not even be mounted;
// see utils/shortcutEvents.js for why that's the deliberately simple
// choice here over prop drilling or a new context.
function WorkspaceShell({
  refreshSignal,
  document,
  selectedDocuments,
  contentLoading,
  cachedContent,
  onOpen,
  onRename,
  onDelete,
  onToggleSelect,
  onUploadComplete,
}) {
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    function handleKeyDown(event) {
      const isModifierHeld = event.metaKey || event.ctrlKey;
      if (!isModifierHeld) return;
      if (TEXT_ENTRY_TAGS.has(event.target?.tagName)) return;

      const key = event.key.toLowerCase();

      if (key === "k" && !event.shiftKey) {
        event.preventDefault();
        emitShortcutEvent(FOCUS_SEARCH_EVENT);
      } else if (key === "/" && !event.shiftKey) {
        event.preventDefault();
        setShortcutsOpen(true);
      } else if (key === "n" && event.shiftKey) {
        // Note: Chrome reserves Ctrl/Cmd+Shift+N for "New Incognito
        // Window" at the browser-chrome level — preventDefault() here
        // can't override that, so this combo simply won't reach the
        // page in Chrome. It works as documented in Firefox and
        // Safari. Left in per the brief's suggested shortcut list
        // rather than substituting a different combo unprompted.
        event.preventDefault();
        emitShortcutEvent(NEW_CONVERSATION_EVENT);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col bg-surface lg:h-screen lg:overflow-hidden">
      {/* Visually hidden until focused — lets a keyboard user jump
          straight past the library panel to the study workspace,
          rather than tabbing through every document row first. */}
      <a
        href="#study-workspace"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to study workspace
      </a>

      <TopBar onOpenShortcuts={() => setShortcutsOpen(true)} />

      <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
        <aside
          aria-label="Document library"
          className="min-w-0 shrink-0 border-b border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[22%] lg:min-w-[260px] lg:max-w-[360px] lg:overflow-hidden lg:border-b-0 lg:border-r lg:p-8"
        >
          <LibraryPanel
            refreshSignal={refreshSignal}
            activeDocumentId={document?.id ?? null}
            selectedDocumentIds={selectedDocuments.map((selected) => selected.id)}
            onOpen={onOpen}
            onRename={onRename}
            onDelete={onDelete}
            onToggleSelect={onToggleSelect}
            onUploadComplete={onUploadComplete}
          />
        </aside>

        <main
          id="study-workspace"
          tabIndex={-1}
          aria-label="Study workspace"
          className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-y-auto lg:p-10"
        >
          <StudyWorkspace
            document={document}
            contentLoading={contentLoading}
            cachedContent={cachedContent}
          />
        </main>

        <aside
          aria-label="AI assistant"
          className="min-w-0 shrink-0 border-t border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[26%] lg:min-w-[300px] lg:max-w-[420px] lg:overflow-hidden lg:border-t-0 lg:border-l lg:p-6"
        >
          <AssistantPanel selectedDocuments={selectedDocuments} onToggleSelect={onToggleSelect} />
        </aside>
      </div>

      {shortcutsOpen && <ShortcutsDialog onClose={() => setShortcutsOpen(false)} />}
    </div>
  );
}

export default WorkspaceShell;
