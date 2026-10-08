import { useState } from "react";
import { isGuestLimitError } from "../api/errors.js";
import GuestLimitNotice from "./GuestLimitNotice.jsx";
import LibraryPanel from "./LibraryPanel.jsx";
import Modal from "./Modal.jsx";
import { classifyStudyReadiness, describeStudyReadiness } from "../utils/documentReadiness.js";
import {
  MAX_REVISION_DOCUMENTS,
  MAX_REVISION_QUESTION_COUNT,
  MIN_REVISION_QUESTION_COUNT,
  REVISION_DIFFICULTIES,
  REVISION_MODES,
  REVISION_QUESTION_TYPES,
  buildCreateSessionPayload,
  createInitialSetupState,
  validateSetupState,
} from "../utils/revisionState.js";

function RevisionSetup({
  onStartSession,
  isCreating = false,
  creationError = null,
  setupState: controlledSetupState,
  onSetupStateChange,
  selectedDocuments: controlledSelectedDocuments,
  onSelectedDocumentsChange,
  initialSetupState = null,
  initialSelectedDocuments = [],
}) {
  const [internalSetupState, setInternalSetupState] = useState(() => initialSetupState || createInitialSetupState());
  const [internalSelectedDocuments, setInternalSelectedDocuments] = useState(() => initialSelectedDocuments || []);

  const setupState = controlledSetupState !== undefined ? controlledSetupState : internalSetupState;
  const setSetupState = onSetupStateChange || setInternalSetupState;

  const selectedDocuments = controlledSelectedDocuments !== undefined ? controlledSelectedDocuments : internalSelectedDocuments;
  const setSelectedDocuments = onSelectedDocumentsChange || setInternalSelectedDocuments;
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [refreshSignal, setRefreshSignal] = useState(0);

  // Classify selected documents according to their readiness
  const categorized = classifyStudyReadiness(selectedDocuments);
  const readinessMessage = describeStudyReadiness(categorized);

  const validation = validateSetupState({
    selectedDocuments,
    questionCount: setupState.questionCount,
    difficulty: setupState.difficulty,
    mode: setupState.mode,
    questionType: setupState.questionType,
  });

  function handleToggleDocSelect(doc) {
    setSelectedDocuments((prev) => {
      const exists = prev.some((d) => d.id === doc.id);
      if (exists) {
        return prev.filter((d) => d.id !== doc.id);
      }
      if (prev.length >= MAX_REVISION_DOCUMENTS) {
        return prev;
      }
      return [...prev, doc];
    });
  }

  function handleRemoveDoc(docId) {
    setSelectedDocuments((prev) => prev.filter((d) => d.id !== docId));
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!validation.isValid || isCreating) return;

    const payload = buildCreateSessionPayload(setupState, selectedDocuments);
    onStartSession(payload);
  }

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-accent-100 px-2 py-0.5 text-xs font-semibold text-accent-700">
            Revision 2.0
          </span>
        </div>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Start a Revision Session
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Reinforce your knowledge across 1 to 10 documents with AI-grounded practice questions,
          instant evaluation, and attempt tracking.
        </p>
      </div>

      {/* Error notices */}
      {creationError && isGuestLimitError(creationError) && (
        <div className="mb-6">
          <GuestLimitNotice error={creationError} />
        </div>
      )}
      {creationError && !isGuestLimitError(creationError) && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-semibold">Session Creation Failed</p>
          <p className="mt-1">{creationError.message || String(creationError)}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Document Selection Section */}
        <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Study Documents
                <span className="ml-2 font-normal text-slate-500">
                  ({selectedDocuments.length} of {MAX_REVISION_DOCUMENTS} selected)
                </span>
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Select 1 to 10 documents with readable text to synthesize revision questions from.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsPickerOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-surface px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
              </svg>
              {selectedDocuments.length > 0 ? "Change Documents" : "Select Documents"}
            </button>
          </div>

          {/* Selected Document Chips */}
          {selectedDocuments.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {selectedDocuments.map((doc) => {
                const isReady = doc.status === "ready" && (doc.character_count ?? 0) > 0;
                return (
                  <span
                    key={doc.id}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                      isReady
                        ? "border border-accent-200 bg-accent-50 text-accent-800"
                        : "border border-amber-200 bg-amber-50 text-amber-800"
                    }`}
                  >
                    <span className="max-w-[200px] truncate" title={doc.original_filename}>
                      {doc.original_filename}
                    </span>
                    {!isReady && (
                      <span className="text-[10px] text-amber-600">
                        ({doc.status !== "ready" ? doc.status : "no text"})
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveDoc(doc.id)}
                      aria-label={`Remove ${doc.original_filename}`}
                      className="ml-0.5 rounded-full p-0.5 hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                    >
                      <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                        <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
                      </svg>
                    </button>
                  </span>
                );
              })}
            </div>
          ) : (
            <div className="mt-4 rounded-lg border border-dashed border-slate-200 p-6 text-center">
              <p className="text-xs text-slate-500">
                No documents selected yet. Click &quot;Select Documents&quot; to pick documents from your library.
              </p>
            </div>
          )}

          {/* Readiness notification */}
          {readinessMessage && (
            <div
              className={`mt-4 rounded-lg border p-3 text-xs ${
                categorized.isNoneReadable
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              {readinessMessage}
            </div>
          )}
        </div>

        {/* Configuration Controls */}
        <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-xs space-y-6">
          <h2 className="text-sm font-semibold text-slate-900">Session Configuration</h2>

          {/* Session Title (Optional) */}
          <div>
            <label htmlFor="revision-title" className="block text-xs font-medium text-slate-700">
              Session Title <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              id="revision-title"
              type="text"
              value={setupState.title}
              onChange={(e) => setSetupState((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="e.g. Midterm Biology Review"
              maxLength={200}
              className="mt-1.5 block w-full rounded-md border border-slate-300 bg-surface px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
            />
          </div>

          {/* Question Type Selection */}
          <div>
            <span className="block text-xs font-medium text-slate-700">Question Format</span>
            <div className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              {REVISION_QUESTION_TYPES.map((type) => {
                const isSelected = setupState.questionType === type.id;
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setSetupState((prev) => ({ ...prev, questionType: type.id }))}
                    className={`flex flex-col rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                      isSelected
                        ? "border-accent-600 bg-accent-50/60 ring-1 ring-accent-600"
                        : "border-slate-200 bg-surface hover:border-slate-300 hover:bg-slate-50/50"
                    }`}
                  >
                    <span className="text-sm font-medium text-slate-900">{type.label}</span>
                    <span className="mt-1 text-xs text-slate-500">{type.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Mode Selection */}
          <div>
            <span className="block text-xs font-medium text-slate-700">Session Mode</span>
            <div className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              {REVISION_MODES.map((mode) => {
                const isSelected = setupState.mode === mode.id;
                return (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setSetupState((prev) => ({ ...prev, mode: mode.id }))}
                    className={`flex flex-col rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                      isSelected
                        ? "border-accent-600 bg-accent-50/60 ring-1 ring-accent-600"
                        : "border-slate-200 bg-surface hover:border-slate-300 hover:bg-slate-50/50"
                    }`}
                  >
                    <span className="text-sm font-medium text-slate-900">{mode.label}</span>
                    <span className="mt-1 text-xs text-slate-500">{mode.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Difficulty Selection */}
          <div>
            <span className="block text-xs font-medium text-slate-700">Difficulty Level</span>
            <div className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              {REVISION_DIFFICULTIES.map((diff) => {
                const isSelected = setupState.difficulty === diff.id;
                return (
                  <button
                    key={diff.id}
                    type="button"
                    onClick={() => setSetupState((prev) => ({ ...prev, difficulty: diff.id }))}
                    className={`flex flex-col rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                      isSelected
                        ? "border-accent-600 bg-accent-50/60 ring-1 ring-accent-600"
                        : "border-slate-200 bg-surface hover:border-slate-300 hover:bg-slate-50/50"
                    }`}
                  >
                    <span className="text-sm font-medium text-slate-900">{diff.label}</span>
                    <span className="mt-1 text-xs text-slate-500">{diff.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Question Count Selection */}
          <div>
            <label htmlFor="question-count" className="block text-xs font-medium text-slate-700">
              Number of Questions ({MIN_REVISION_QUESTION_COUNT}–{MAX_REVISION_QUESTION_COUNT})
            </label>
            <div className="mt-2 flex items-center gap-3">
              <input
                id="question-count"
                type="range"
                min={MIN_REVISION_QUESTION_COUNT}
                max={MAX_REVISION_QUESTION_COUNT}
                value={setupState.questionCount}
                onChange={(e) =>
                  setSetupState((prev) => ({
                    ...prev,
                    questionCount: Number.parseInt(e.target.value, 10),
                  }))
                }
                className="h-2 w-48 cursor-pointer rounded-lg bg-slate-200 accent-accent-600"
              />
              <span className="inline-flex h-8 w-12 items-center justify-center rounded-md border border-slate-300 bg-surface text-sm font-semibold text-slate-900">
                {setupState.questionCount}
              </span>
            </div>
          </div>
        </div>

        {/* Submit Launcher Button */}
        <div className="flex flex-col items-end gap-2">
          {!validation.isValid && validation.error && (
            <p className="text-xs text-amber-700">{validation.error}</p>
          )}
          <button
            type="submit"
            disabled={!validation.isValid || isCreating}
            className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isCreating ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span>Generating Revision Session...</span>
              </>
            ) : (
              <span>Start Revision Session</span>
            )}
          </button>
        </div>
      </form>

      {/* Document Picker Modal */}
      {isPickerOpen && (
        <Modal
          title="Select Revision Documents"
          description="Choose up to 10 documents to synthesize revision questions from."
          onClose={() => setIsPickerOpen(false)}
          maxWidthClassName="max-w-2xl"
        >
          <div className="max-h-[60vh] overflow-y-auto">
            <LibraryPanel
              refreshSignal={refreshSignal}
              selectedDocumentIds={selectedDocuments.map((d) => d.id)}
              selectable={true}
              selectionScope="revision"
              maxSelected={MAX_REVISION_DOCUMENTS}
              onToggleSelect={handleToggleDocSelect}
              onUploadComplete={() => setRefreshSignal((prev) => prev + 1)}
            />
          </div>
          <div className="mt-4 flex justify-end border-t border-slate-200 pt-3">
            <button
              type="button"
              onClick={() => setIsPickerOpen(false)}
              className="rounded-md bg-accent-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              Done Selecting
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default RevisionSetup;
