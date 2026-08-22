import { useEffect, useState } from "react";
import EmptyWorkspaceState from "./EmptyWorkspaceState";
import FlashcardsPanel from "./FlashcardsPanel";
import MindMapPanel from "./MindMapPanel";
import NoReadableTextState from "./NoReadableTextState";
import QuizPanel from "./QuizPanel";
import SummaryPanel from "./SummaryPanel";
import { hasNoReadableText } from "../utils/documentReadiness";
import { loadActiveStudyTab, saveActiveStudyTab } from "../utils/persistence";

// Maps the raw backend status value to copy a student should actually
// read, rather than the internal state name ("ready", "failed").
// Moved from the old combined HomePage (now StudyPage, since this milestone's
// Home is a different, lightweight dashboard page) — used only by this panel's
// document-info block.
function statusLabel(status) {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Couldn't process this file";
  return status;
}

function statusPillClasses(status) {
  if (status === "ready") return "bg-emerald-50 text-emerald-700";
  if (status === "failed") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}

function formatFileSize(bytes) {
  if (bytes === null || bytes === undefined) return null;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.max(1, Math.round(kb))} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatPageCount(pageCount) {
  if (pageCount === null || pageCount === undefined) return null;
  return `${pageCount} ${pageCount === 1 ? "page" : "pages"}`;
}

// DOCX (and any future format without a page tree) has no page
// count — falls back to a file-type label derived from the extension
// itself, the same way DocumentList.jsx does, so this metadata slot
// is always populated instead of silently disappearing for some
// formats.
function formatPageCountOrFileType(document) {
  const pageCount = formatPageCount(document.page_count);
  if (pageCount) return pageCount;
  const lastDot = document.original_filename.lastIndexOf(".");
  if (lastDot <= 0) return null;
  return document.original_filename.slice(lastDot + 1).toUpperCase();
}

// The four study tools, tabbed rather than stacked (see StudyWorkspace
// below for why this milestone introduces the tab bar). Order here
// also defines tab order in the UI.
const STUDY_TABS = [
  { id: "summary", label: "Summary" },
  { id: "flashcards", label: "Flashcards" },
  { id: "quiz", label: "Quiz" },
  { id: "mindmap", label: "Mind Map" },
];
const STUDY_TAB_IDS = STUDY_TABS.map((tab) => tab.id);

// The center panel (≈60%) of the workspace: the open document's info
// block, then a tab bar switching between its Summary / Flashcards /
// Quiz / Mind Map.
//
// Milestone 1 rendered all four study panels stacked, one below the
// other, with tabs deliberately deferred ("only one study mode
// visible at a time is a later milestone"). This milestone (V2.1
// Milestone 2, Workspace Session Persistence) is required to restore
// "whether the user was viewing Summary/Flashcards/Quiz/Mind Map"
// after a refresh — which only means something once there's a single
// active tab to restore. So the tab bar below is introduced here, as
// the minimal prerequisite for that requirement: still frontend-only,
// same visual language as the rest of the workspace, no behavior
// changes to the four panels themselves.
//
// The info block itself used to also show a preview of the extracted
// text (with a Read More/Show Less toggle) above the tab bar. That's
// gone as of the V2.2 library/workspace polish pass — the Summary tab
// one click away already explains the document, so a second, raw
// excerpt of it here was duplicated information competing for the
// same space. What's left is just enough to orient the student
// (title, status, and the same at-a-glance metadata the library
// shows) before they get to the tools they're actually here for.
function StudyWorkspace({ document, contentLoading, cachedContent, onContentGenerated }) {
  // Which study tool is showing. This is a workspace-wide preference
  // (which tool the student was using), not something scoped to a
  // particular document, so it's read once here rather than threaded
  // through `document` — switching to a different document keeps
  // whichever tab was active, the same way switching files in an
  // editor keeps the same side panel open. Falls back to "summary" if
  // storage is empty or holds a value from an older schema.
  const [activeTab, setActiveTab] = useState(() => {
    const stored = loadActiveStudyTab();
    return STUDY_TAB_IDS.includes(stored) ? stored : STUDY_TAB_IDS[0];
  });

  useEffect(() => {
    saveActiveStudyTab(activeTab);
  }, [activeTab]);

  if (!document) {
    return <EmptyWorkspaceState />;
  }

  const noReadableText = hasNoReadableText(document);
  // The pre-existing "very little text" advisory line remains for the
  // 1-49 character range (still enough for the AI to at least attempt
  // something from real, if sparse, content) — it no longer covers
  // character_count === 0, which is the stronger, generation-blocking
  // case now called out on its own, in the same amber tone, right
  // below it.
  const extractedVeryLittleText =
    document.status === "ready" && !noReadableText && document.character_count < 50;
  const pageOrType = formatPageCountOrFileType(document);
  const fileSize = formatFileSize(document.file_size_bytes);

  return (
    <div className="space-y-6">
      <div className="space-y-1.5 border-b border-slate-100 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-lg font-semibold text-slate-900">{document.original_filename}</p>
          <span
            className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${statusPillClasses(
              document.status
            )}`}
          >
            {statusLabel(document.status)}
          </span>
        </div>

        <p className="flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
          {pageOrType && (
            <span title={formatPageCount(document.page_count) ? "Page count" : "File type"}>
              {pageOrType}
            </span>
          )}
          {fileSize && (
            <>
              <span aria-hidden="true">&middot;</span>
              <span title="File size">{fileSize}</span>
            </>
          )}
        </p>

        {extractedVeryLittleText && (
          <p className="text-xs text-amber-600">
            Very little text was extracted. This might be a scanned/image-only document, which
            isn&apos;t supported yet.
          </p>
        )}

        {noReadableText && (
          <p className="text-xs text-amber-700">
            No readable text was detected in this document, so Summary, Flashcards, Quiz, and
            Mind Map are unavailable for it. This usually means it&apos;s a scanned or
            image-only file.
          </p>
        )}

        {document.status === "failed" && (
          <p className="text-sm text-red-600">
            We couldn&apos;t read this file — it may be corrupted, password-protected, or in an
            unsupported format. Try uploading a different file.
          </p>
        )}
      </div>

      {document.status === "ready" && (
        <>
          <div className="flex flex-wrap gap-1 border-b border-slate-200" role="tablist">
            {STUDY_TABS.map((tab) => {
              const isActive = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveTab(tab.id)}
                  className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset ${
                    isActive
                      ? "border-accent-600 text-accent-700"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {contentLoading || !cachedContent ? (
            <p className="text-center text-sm text-slate-500">Loading saved content...</p>
          ) : noReadableText ? (
            // No panel is mounted here at all — not just visually
            // hidden — so there's no "Generate" button to click and
            // no way this state can trigger an API call, let alone an
            // AI request. See NoReadableTextState.jsx.
            <NoReadableTextState tool={activeTab} />
          ) : (
            <div>
              {activeTab === "summary" && (
                <SummaryPanel
                  key={`summary-${document.id}`}
                  documentId={document.id}
                  initialSummary={cachedContent.summary}
                  onGenerated={(value) => onContentGenerated("summary", value)}
                />
              )}
              {activeTab === "flashcards" && (
                <FlashcardsPanel
                  key={`flashcards-${document.id}`}
                  documentId={document.id}
                  initialFlashcards={cachedContent.flashcards}
                  onGenerated={(value) => onContentGenerated("flashcards", value)}
                />
              )}
              {activeTab === "quiz" && (
                <QuizPanel
                  key={`quiz-${document.id}`}
                  documentId={document.id}
                  initialQuestions={cachedContent.quiz}
                  onGenerated={(value) => onContentGenerated("quiz", value)}
                />
              )}
              {activeTab === "mindmap" && (
                <MindMapPanel
                  key={`mindmap-${document.id}`}
                  documentId={document.id}
                  initialMindmap={cachedContent.mindmap}
                  onGenerated={(value) => onContentGenerated("mindmap", value)}
                />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default StudyWorkspace;
