import { useState } from "react";
import { createRevisionSession } from "../api/revision.js";
import RevisionActiveRunner from "../components/RevisionActiveRunner.jsx";
import RevisionHistoryView from "../components/RevisionHistoryView.jsx";
import RevisionResultsView from "../components/RevisionResultsView.jsx";
import RevisionSetup from "../components/RevisionSetup.jsx";
import { hydrateDocumentIds } from "../utils/documentHydration.js";
import { createInitialSetupState, prepareRetakeSetup } from "../utils/revisionState.js";

/**
 * Top-level page for Revision Experience 2.0 (V3 Milestone 4 Phase 4).
 *
 * Coordinates:
 * 1. Revision Setup (New Session / Retake)
 * 2. Revision Session History
 * 3. Active Session Runner (New or Resumed)
 * 4. Completed Session Results Review
 */
function RevisionPage() {
  const [viewMode, setViewMode] = useState("launcher"); // "launcher" | "history" | "runner" | "results"
  const [activeSession, setActiveSession] = useState(null);
  const [reviewingSession, setReviewingSession] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [creationError, setCreationError] = useState(null);

  // Setup form state preserved at page level across launcher <-> history view switches
  const [setupState, setSetupState] = useState(() => createInitialSetupState());
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  async function handleStartSession(payload) {
    setIsCreating(true);
    setCreationError(null);

    try {
      const session = await createRevisionSession(payload);
      setActiveSession(session);
      setViewMode("runner");
      // Reset setup state for subsequent new sessions
      setSetupState(createInitialSetupState());
      setSelectedDocuments([]);
    } catch (error) {
      setCreationError(error);
    } finally {
      setIsCreating(false);
    }
  }

  function handleResumeSession(sessionDetail) {
    // Resume in-progress session: restore persisted questions and attempts without regeneration
    setActiveSession(sessionDetail);
    setReviewingSession(null);
    setViewMode("runner");
  }

  function handleReviewSession(sessionDetail) {
    // Review completed session
    setReviewingSession(sessionDetail);
    setViewMode("results");
  }

  async function handleRetakeSession(sessionDetail) {
    // Retake creates a brand new session using the original configuration without mutating the completed session
    const setupConfig = prepareRetakeSetup(sessionDetail);
    setSetupState(setupConfig);

    // Hydrate existing documents; deleted documents will be automatically omitted
    if (Array.isArray(sessionDetail.document_ids) && sessionDetail.document_ids.length > 0) {
      const docs = await hydrateDocumentIds(sessionDetail.document_ids);
      setSelectedDocuments(docs);
    } else {
      setSelectedDocuments([]);
    }

    setActiveSession(null);
    setReviewingSession(null);
    setViewMode("launcher");
  }

  function handleExitToHistory() {
    setActiveSession(null);
    setReviewingSession(null);
    setViewMode("history");
  }

  function handleExitToLauncher() {
    setActiveSession(null);
    setReviewingSession(null);
    setViewMode("launcher");
  }

  const showSubNav = viewMode === "launcher" || viewMode === "history";

  return (
    <main aria-label="Revision" className="min-w-0 flex-1 min-h-0 overflow-y-auto bg-slate-50/50 py-6">
      {/* Sub-Navigation between New Session and History */}
      {showSubNav && (
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 mb-6">
          <div className="inline-flex rounded-lg border border-slate-200 bg-surface p-1 shadow-2xs">
            <button
              type="button"
              onClick={() => setViewMode("launcher")}
              className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                viewMode === "launcher"
                  ? "bg-accent-600 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              New Revision
            </button>
            <button
              type="button"
              onClick={() => setViewMode("history")}
              className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                viewMode === "history"
                  ? "bg-accent-600 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Session History
            </button>
          </div>
        </div>
      )}

      {/* View router */}
      {viewMode === "runner" && activeSession && (
        <RevisionActiveRunner
          session={activeSession}
          onExit={handleExitToHistory}
          onReview={(completedSession) => handleReviewSession(completedSession)}
        />
      )}

      {viewMode === "results" && reviewingSession && (
        <RevisionResultsView
          session={reviewingSession}
          onBackToHistory={handleExitToHistory}
          onRetake={(session) => handleRetakeSession(session)}
        />
      )}

      {viewMode === "history" && (
        <RevisionHistoryView
          onStartNewSession={handleExitToLauncher}
          onResumeSession={handleResumeSession}
          onReviewSession={handleReviewSession}
          onRetakeSession={handleRetakeSession}
        />
      )}

      {viewMode === "launcher" && (
        <RevisionSetup
          setupState={setupState}
          onSetupStateChange={setSetupState}
          selectedDocuments={selectedDocuments}
          onSelectedDocumentsChange={setSelectedDocuments}
          onStartSession={handleStartSession}
          isCreating={isCreating}
          creationError={creationError}
        />
      )}
    </main>
  );
}

export default RevisionPage;
