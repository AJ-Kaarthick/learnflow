import { useEffect, useState } from "react";
import EmptyWorkspaceState from "./EmptyWorkspaceState";
import ExpandableText from "./ExpandableText";
import FlashcardsPanel from "./FlashcardsPanel";
import MindMapPanel from "./MindMapPanel";
import QuizPanel from "./QuizPanel";
import SummaryPanel from "./SummaryPanel";
import { loadActiveStudyTab, saveActiveStudyTab } from "../utils/persistence";

// The backend truncates `text_preview` at a fixed character count,
// which can land mid-word (e.g. "...system s"). Trimming back to the
// last whole word before adding the ellipsis guarantees the preview
// always ends cleanly, without touching how the backend generates it.
function cleanTruncatedPreview(preview, isTruncated) {
  if (!isTruncated) return preview;
  const trimmedToWordBoundary = preview.replace(/\s+\S*$/, "");
  return `${trimmedToWordBoundary || preview}…`;
}

// Maps the raw backend status value to copy a student should actually
// read, rather than the internal state name ("ready", "failed").
// Moved from HomePage — used only by this panel's document-info block.
function statusLabel(status) {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Couldn't process this file";
  return status;
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
function StudyWorkspace({ document, contentLoading, cachedContent }) {
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

  const extractedVeryLittleText =
    document.status === "ready" && document.character_count < 50;

  return (
    <div className="space-y-6">
      <div className="space-y-2 border-b border-slate-100 pb-6">
        <p className="text-lg font-semibold text-slate-900">{document.original_filename}</p>
        <p className="text-xs text-slate-500">
          Status: {statusLabel(document.status)}
          {document.status === "ready" && (
            <> &middot; {document.character_count} characters extracted</>
          )}
        </p>

        {extractedVeryLittleText && (
          <p className="text-xs text-amber-600">
            Very little text was extracted. This might be a scanned/image-only PDF, which
            isn&apos;t supported yet.
          </p>
        )}

        {document.status === "failed" && (
          <p className="text-sm text-red-600">
            We couldn&apos;t read this PDF — it may be corrupted or scanned without a text layer.
            Try uploading a different file.
          </p>
        )}

        {document.status === "ready" && (
          <ExpandableText
            text={cleanTruncatedPreview(
              document.text_preview,
              document.character_count > document.text_preview.length
            )}
            className="max-w-3xl"
            textClassName="text-sm text-slate-700"
            fadeFromClassName="from-surface"
          />
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
          ) : (
            <div>
              {activeTab === "summary" && (
                <SummaryPanel
                  key={`summary-${document.id}`}
                  documentId={document.id}
                  initialSummary={cachedContent.summary}
                />
              )}
              {activeTab === "flashcards" && (
                <FlashcardsPanel
                  key={`flashcards-${document.id}`}
                  documentId={document.id}
                  initialFlashcards={cachedContent.flashcards}
                />
              )}
              {activeTab === "quiz" && (
                <QuizPanel
                  key={`quiz-${document.id}`}
                  documentId={document.id}
                  initialQuestions={cachedContent.quiz}
                />
              )}
              {activeTab === "mindmap" && (
                <MindMapPanel
                  key={`mindmap-${document.id}`}
                  documentId={document.id}
                  initialMindmap={cachedContent.mindmap}
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
