import AssistantPanel from "./AssistantPanel";
import LibraryPanel from "./LibraryPanel";
import StudyWorkspace from "./StudyWorkspace";
import TopBar from "./TopBar";

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
  return (
    <div className="flex flex-col bg-white lg:h-screen lg:overflow-hidden">
      <TopBar />

      <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
        <aside className="min-w-0 shrink-0 border-b border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[22%] lg:min-w-[260px] lg:max-w-[360px] lg:overflow-hidden lg:border-b-0 lg:border-r lg:p-8">
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

        <section className="min-w-0 flex-1 p-6 lg:h-full lg:overflow-y-auto lg:p-10">
          <StudyWorkspace
            document={document}
            contentLoading={contentLoading}
            cachedContent={cachedContent}
          />
        </section>

        <aside className="min-w-0 shrink-0 border-t border-slate-200 bg-slate-50/60 p-6 lg:h-full lg:w-[26%] lg:min-w-[300px] lg:max-w-[420px] lg:overflow-hidden lg:border-t-0 lg:border-l lg:p-6">
          <AssistantPanel selectedDocuments={selectedDocuments} onToggleSelect={onToggleSelect} />
        </aside>
      </div>
    </div>
  );
}

export default WorkspaceShell;
