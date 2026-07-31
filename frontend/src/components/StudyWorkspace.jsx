import EmptyWorkspaceState from "./EmptyWorkspaceState";
import FlashcardsPanel from "./FlashcardsPanel";
import MindMapPanel from "./MindMapPanel";
import QuizPanel from "./QuizPanel";
import SummaryPanel from "./SummaryPanel";

// Maps the raw backend status value to copy a student should actually
// read, rather than the internal state name ("ready", "failed").
// Moved from HomePage — used only by this panel's document-info block.
function statusLabel(status) {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Couldn't process this file";
  return status;
}

// The center panel (≈60%) of the workspace. For this milestone it's
// only the *container* that used to be several stacked page sections
// in HomePage: the open document's info block, then its Summary /
// Flashcards / Quiz / Mind Map, one below the other exactly as
// before. Tabs (only one study mode visible at a time) are a later
// milestone — see the V2.1 blueprint §10 Phase 2 — so all four panels
// still render together here, just inside the new column instead of
// the old full-width page.
function StudyWorkspace({ document, contentLoading, cachedContent }) {
  if (!document) {
    return <EmptyWorkspaceState />;
  }

  const extractedVeryLittleText =
    document.status === "ready" && document.character_count < 50;

  return (
    <div className="space-y-8">
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
          <p className="max-w-3xl text-sm text-slate-700 whitespace-pre-wrap">
            {document.text_preview}
            {document.character_count > document.text_preview.length && "…"}
          </p>
        )}
      </div>

      {document.status === "ready" &&
        (contentLoading || !cachedContent ? (
          <p className="text-center text-sm text-slate-500">Loading saved content...</p>
        ) : (
          <div className="space-y-6">
            <SummaryPanel
              key={`summary-${document.id}`}
              documentId={document.id}
              initialSummary={cachedContent.summary}
            />
            <FlashcardsPanel
              key={`flashcards-${document.id}`}
              documentId={document.id}
              initialFlashcards={cachedContent.flashcards}
            />
            <QuizPanel
              key={`quiz-${document.id}`}
              documentId={document.id}
              initialQuestions={cachedContent.quiz}
            />
            <MindMapPanel
              key={`mindmap-${document.id}`}
              documentId={document.id}
              initialMindmap={cachedContent.mindmap}
            />
          </div>
        ))}
    </div>
  );
}

export default StudyWorkspace;
