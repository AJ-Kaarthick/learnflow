import { useState } from "react";
import { createRevisionSession } from "../api/revision.js";
import RevisionActiveRunner from "../components/RevisionActiveRunner.jsx";
import RevisionSetup from "../components/RevisionSetup.jsx";

/**
 * Top-level page for Revision Experience 2.0 (V3 Milestone 4 Phase 3).
 *
 * Coordinates the Revision setup launcher and active runner workflows.
 * The backend is authoritative for question generation, evaluation,
 * attempt immutability, and session status.
 */
function RevisionPage() {
  const [activeSession, setActiveSession] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [creationError, setCreationError] = useState(null);

  async function handleStartSession(payload) {
    setIsCreating(true);
    setCreationError(null);

    try {
      const session = await createRevisionSession(payload);
      setActiveSession(session);
    } catch (error) {
      setCreationError(error);
    } finally {
      setIsCreating(false);
    }
  }

  function handleExit() {
    setActiveSession(null);
    setCreationError(null);
  }

  return (
    <div className="min-h-full bg-slate-50/50 py-6">
      {activeSession ? (
        <RevisionActiveRunner session={activeSession} onExit={handleExit} />
      ) : (
        <RevisionSetup
          onStartSession={handleStartSession}
          isCreating={isCreating}
          creationError={creationError}
        />
      )}
    </div>
  );
}

export default RevisionPage;
