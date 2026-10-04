import { useEffect, useState } from "react";
import EmptyWorkspaceState from "./EmptyWorkspaceState";
import FlashcardsPanel from "./FlashcardsPanel";
import LearnPanel from "./LearnPanel.jsx";
import VisualizePanel from "./VisualizePanel.jsx";
import MindMapPanel from "./MindMapPanel";
import NoReadableTextState from "./NoReadableTextState";
import QuizPanel from "./QuizPanel";
import SummaryPanel from "./SummaryPanel";
import { classifyStudyReadiness, describeStudyReadiness, hasNoReadableText } from "../utils/documentReadiness";
import { createInitialLearnSession } from "../utils/learnState.js";
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

// The study tools, tabbed rather than stacked.
// Order here also defines tab order in the UI: Learn | Visualize | Summary | Flashcards | Quiz | Mind Map.
const STUDY_TABS = [
  { id: "learn", label: "Learn" },
  { id: "visualize", label: "Visualize" },
  { id: "summary", label: "Summary" },
  { id: "flashcards", label: "Flashcards" },
  { id: "quiz", label: "Quiz" },
  { id: "mindmap", label: "Mind Map" },
];
const STUDY_TAB_IDS = STUDY_TABS.map((tab) => tab.id);

// The center panel of the workspace:
// - In single-document mode: the open document's info block, then tabs.
// - In multi-document mode: document chip row (1-10 documents) with add/remove
//   actions, readiness status, active focus indicator, and tabs for the focused document.
function StudyWorkspace({
  document,
  selectedDocuments = [],
  contentLoading,
  cachedContent,
  onContentGenerated,
  onSelectActiveDocument,
  onRemoveDocument,
  onOpenDocumentSelector,
  selectionError,
}) {
  const effectiveSelected =
    selectedDocuments && selectedDocuments.length > 0
      ? selectedDocuments
      : document
        ? [document]
        : [];
  const isMultiDocument = effectiveSelected.length > 1;

  // In-memory Learn Mode session state preserved across tab switches in the workspace
  const [learnSession, setLearnSession] = useState(() => createInitialLearnSession());

  // In-memory Visualize Mode session state preserved across tab switches in the workspace
  const [visualizeSession, setVisualizeSession] = useState({ graph: null, depth: "standard" });

  // Which study tool is showing. Workspace-wide preference restored from localStorage.
  const [activeTab, setActiveTab] = useState(() => {
    const stored = loadActiveStudyTab();
    return STUDY_TAB_IDS.includes(stored) ? stored : STUDY_TAB_IDS[0];
  });

  useEffect(() => {
    saveActiveStudyTab(activeTab);
  }, [activeTab]);

  if (!document && effectiveSelected.length === 0) {
    return <EmptyWorkspaceState />;
  }

  const readiness = classifyStudyReadiness(effectiveSelected);
  const readinessExplanation = describeStudyReadiness(readiness);

  // If zero selected documents are readable, block study generation with an explanation
  if (readiness.isNoneReadable) {
    return (
      <div className="space-y-6">
        {selectionError && (
          <div className="rounded-md bg-red-50 p-2.5 text-xs text-red-700" role="alert">
            {selectionError}
          </div>
        )}

        {/* Selected document chips */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 pb-3">
          <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Study Documents ({effectiveSelected.length}/10):
          </span>
          {effectiveSelected.map((doc) => {
            const isActive = doc.id === document?.id;
            const isUnusable = doc.status !== "ready" || (doc.character_count ?? 0) === 0;
            return (
              <span
                key={doc.id}
                className={`inline-flex max-w-full items-center gap-1.5 rounded-full py-1 pl-3 pr-2 text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-accent-600 text-white shadow-sm"
                    : isUnusable
                      ? "border border-amber-300 bg-amber-100 text-amber-800"
                      : "bg-accent-50 text-accent-800 hover:bg-accent-100"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectActiveDocument?.(doc)}
                  className="max-w-[180px] truncate text-left focus-visible:outline-none"
                  title={doc.original_filename}
                >
                  {doc.original_filename}
                </button>
                {onRemoveDocument && (
                  <button
                    type="button"
                    onClick={() => onRemoveDocument(doc.id)}
                    aria-label={`Remove ${doc.original_filename} from study`}
                    className={`shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 ${
                      isActive ? "text-white/80 hover:text-white" : "text-accent-400 hover:text-accent-700"
                    }`}
                  >
                    &times;
                  </button>
                )}
              </span>
            );
          })}
          {effectiveSelected.length < 10 && onOpenDocumentSelector && (
            <button
              type="button"
              onClick={onOpenDocumentSelector}
              className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:border-accent-400 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
                <path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4Z" />
              </svg>
              Add
            </button>
          )}
        </div>

        <div
          className="space-y-2 rounded-xl border border-amber-300 bg-amber-50/80 p-6 text-center"
          role="alert"
        >
          <p className="text-sm font-semibold text-amber-900">
            No readable documents available for study
          </p>
          <p className="mx-auto max-w-lg text-xs leading-relaxed text-amber-800">
            {readinessExplanation}
          </p>
        </div>
      </div>
    );
  }

  const noReadableText = document ? hasNoReadableText(document) : false;
  const extractedVeryLittleText =
    document?.status === "ready" && !noReadableText && (document.character_count ?? 0) < 50;
  const pageOrType = document ? formatPageCountOrFileType(document) : null;
  const fileSize = document ? formatFileSize(document.file_size_bytes) : null;

  return (
    <div className="space-y-6">
      {selectionError && (
        <div className="rounded-md bg-red-50 p-2.5 text-xs text-red-700" role="alert">
          {selectionError}
        </div>
      )}

      {isMultiDocument ? (
        <div className="space-y-3 border-b border-slate-100 pb-4">
          {/* Multi-document chip row */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Study Documents ({effectiveSelected.length}/10):
            </span>
            {effectiveSelected.map((doc) => {
              const isActive = doc.id === document?.id;
              const isUnusable = doc.status !== "ready" || (doc.character_count ?? 0) === 0;
              return (
                <span
                  key={doc.id}
                  className={`inline-flex max-w-full items-center gap-1.5 rounded-full py-1 pl-3 pr-2 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-accent-600 text-white shadow-sm"
                      : isUnusable
                        ? "border border-amber-300 bg-amber-100 text-amber-800"
                        : "bg-accent-50 text-accent-800 hover:bg-accent-100"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectActiveDocument?.(doc)}
                    className="max-w-[180px] truncate text-left focus-visible:outline-none"
                    title={
                      isUnusable
                        ? `${doc.original_filename} (not ready for study)`
                        : `Focus ${doc.original_filename}`
                    }
                  >
                    {doc.original_filename}
                  </button>
                  {onRemoveDocument && (
                    <button
                      type="button"
                      onClick={() => onRemoveDocument(doc.id)}
                      aria-label={`Remove ${doc.original_filename} from study`}
                      className={`shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 ${
                        isActive
                          ? "text-white/80 hover:text-white"
                          : "text-accent-400 hover:text-accent-700"
                      }`}
                    >
                      &times;
                    </button>
                  )}
                </span>
              );
            })}
            {effectiveSelected.length < 10 && onOpenDocumentSelector && (
              <button
                type="button"
                onClick={onOpenDocumentSelector}
                className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:border-accent-400 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
                  <path d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4Z" />
                </svg>
                Add
              </button>
            )}
          </div>

          {/* Advisory banner if some selected documents were excluded */}
          {readinessExplanation && (
            <div
              className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
              role="status"
            >
              {readinessExplanation}
            </div>
          )}

          {/* Orientation notice for multi-document mode */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div>
              <p className="text-xs text-slate-500">
                Multi-document study active ({readiness.readable.length} readable document{readiness.readable.length === 1 ? "" : "s"}).
                {activeTab === "learn" ? (
                  <>
                    {" "}Curriculum and topics synthesized across all{" "}
                    <span className="font-semibold text-slate-800">{effectiveSelected.length}</span> selected documents.
                  </>
                ) : activeTab === "visualize" ? (
                  <>
                    {" "}Concept network synthesized across all{" "}
                    <span className="font-semibold text-slate-800">{effectiveSelected.length}</span> selected documents.
                  </>
                ) : (
                  <>
                    {" "}Showing single-document tools for{" "}
                    <span className="font-semibold text-slate-800">{document?.original_filename}</span>.
                  </>
                )}
              </p>
            </div>
            {document && (
              <span
                className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${statusPillClasses(
                  document.status
                )}`}
              >
                {statusLabel(document.status)}
              </span>
            )}
          </div>
        </div>
      ) : (
        /* Single-document info block (100% backward compatibility) */
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
      )}


      {/* Tab bar and active panel */}
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

      {activeTab === "learn" ? (
        <LearnPanel
          selectedDocuments={effectiveSelected}
          session={learnSession}
          onUpdateSession={setLearnSession}
          isNoneReadable={readiness.isNoneReadable}
        />
      ) : activeTab === "visualize" ? (
        <VisualizePanel
          selectedDocuments={effectiveSelected}
          session={visualizeSession}
          onUpdateSession={setVisualizeSession}
          isNoneReadable={readiness.isNoneReadable}
        />
      ) : document?.status !== "ready" ? (
        <div className="rounded-xl border border-slate-200 bg-surface p-6 text-center text-xs text-slate-500">
          <p className="font-semibold text-slate-700">
            {document?.original_filename || "This document"} is not ready for {STUDY_TABS.find((t) => t.id === activeTab)?.label || "study"}.
          </p>
          <p className="mt-1 text-slate-500">
            Status: {statusLabel(document?.status)}. Focus a ready document from the study selection above, or switch to Learn or Visualize mode to study your readable documents.
          </p>
        </div>
      ) : contentLoading || !cachedContent ? (
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
    </div>
  );
}

export default StudyWorkspace;
