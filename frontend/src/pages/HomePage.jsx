import { useState } from "react";
import { deleteDocument, markDocumentOpened, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import BackendStatus from "../components/BackendStatus";
import ChatPanel from "../components/ChatPanel";
import DocumentLibrary from "../components/DocumentLibrary";
import FlashcardsPanel from "../components/FlashcardsPanel";
import MindMapPanel from "../components/MindMapPanel";
import QuizPanel from "../components/QuizPanel";
import SummaryPanel from "../components/SummaryPanel";
import UploadForm from "../components/UploadForm";

// Maps the raw backend status value to copy a student should actually
// read, rather than the internal state name ("ready", "failed").
function statusLabel(status) {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Couldn't process this file";
  return status;
}

// Loads everything already generated for a document in one place, so
// individual panels don't each decide independently when to fetch —
// HomePage coordinates it once and hands each panel its starting data.
// Failures here fall back to empty/null rather than surfacing an
// error: worst case the panel just shows its normal "not generated
// yet" state, which is still a fully working fallback.
async function loadCachedContent(documentId) {
  const [summary, flashcards, quiz, mindmap] = await Promise.all([
    getSummary(documentId).catch(() => null),
    getFlashcards(documentId).catch(() => []),
    getQuiz(documentId).catch(() => []),
    getMindMap(documentId).catch(() => null),
  ]);
  return { summary, flashcards, quiz, mindmap };
}

function HomePage() {
  // Bumped whenever an action outside DocumentLibrary's own
  // search/sort controls changes the underlying document data (open,
  // rename, delete, upload) so it knows to re-fetch.
  const [refreshSignal, setRefreshSignal] = useState(0);

  const [document, setDocument] = useState(null);
  const [cachedContent, setCachedContent] = useState(null);
  const [contentLoading, setContentLoading] = useState(false);

  // Documents currently included in the chat conversation below —
  // separate from `document` (the single one whose Summary/Flashcards/
  // Quiz/Mind Map are shown), since chatting across several documents
  // doesn't require any of them to be "open" in that sense. Holds
  // {id, original_filename} rather than bare ids so the chat section
  // can show readable chips without needing DocumentLibrary to expose
  // its whole fetched list.
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  function handleToggleSelect(doc) {
    setSelectedDocuments((previous) => {
      const isSelected = previous.some((selected) => selected.id === doc.id);
      if (isSelected) {
        return previous.filter((selected) => selected.id !== doc.id);
      }
      return [...previous, { id: doc.id, original_filename: doc.original_filename }];
    });
  }

  async function openDocument(doc) {
    setDocument(doc);
    setCachedContent(null);

    // Opening a document also includes it in the chat selection, so
    // the old single-document experience (open a document, chat with
    // it, no extra step) still works exactly as before — the user can
    // still add more documents via the library's checkboxes, or
    // uncheck this one, without affecting what's "open".
    setSelectedDocuments((previous) =>
      previous.some((selected) => selected.id === doc.id)
        ? previous
        : [...previous, { id: doc.id, original_filename: doc.original_filename }]
    );

    // Timestamp the open server-side (powers the "Recently Opened"
    // sort) and refresh the library so it reflects the new order.
    // Best-effort: if this fails, opening the document should still
    // work normally.
    markDocumentOpened(doc.id)
      .catch(() => {})
      .finally(() => setRefreshSignal((count) => count + 1));

    if (doc.status !== "ready") return;
    setContentLoading(true);
    const content = await loadCachedContent(doc.id);
    setCachedContent(content);
    setContentLoading(false);
  }

  async function handleUploadComplete(newDocument) {
    await openDocument(newDocument);
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setDocument((previous) => (previous && previous.id === documentId ? updated : previous));
    setSelectedDocuments((previous) =>
      previous.map((selected) =>
        selected.id === documentId
          ? { ...selected, original_filename: updated.original_filename }
          : selected
      )
    );
    setRefreshSignal((count) => count + 1);
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    if (document && document.id === documentId) {
      setDocument(null);
      setCachedContent(null);
    }
    setSelectedDocuments((previous) => previous.filter((selected) => selected.id !== documentId));
    setRefreshSignal((count) => count + 1);
  }

  const extractedVeryLittleText =
    document && document.status === "ready" && document.character_count < 50;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Learn<span className="text-accent-600">Flow</span>
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick up where you left off, or upload a new PDF.
          </p>
        </header>

        <section className="w-full rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <DocumentLibrary
            refreshSignal={refreshSignal}
            activeDocumentId={document?.id ?? null}
            selectedDocumentIds={selectedDocuments.map((selected) => selected.id)}
            onOpen={openDocument}
            onRename={handleRename}
            onDelete={handleDelete}
            onToggleSelect={handleToggleSelect}
          />
        </section>

        <section className="w-full space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <BackendStatus />

          <UploadForm onUploadComplete={handleUploadComplete} />

          {document && (
            <div className="space-y-2 border-t border-slate-200 pt-4">
              <p className="text-sm font-medium text-slate-900">{document.original_filename}</p>
              <p className="text-xs text-slate-500">
                Status: {statusLabel(document.status)}
                {document.status === "ready" && (
                  <>
                    {" "}
                    &middot; {document.character_count} characters extracted
                  </>
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
                  We couldn&apos;t read this PDF — it may be corrupted or scanned without a text
                  layer. Try uploading a different file.
                </p>
              )}

              {document.status === "ready" && (
                <p className="max-w-3xl text-sm text-slate-700 whitespace-pre-wrap">
                  {document.text_preview}
                  {document.character_count > document.text_preview.length && "…"}
                </p>
              )}
            </div>
          )}
        </section>

        {document &&
          document.status === "ready" &&
          (contentLoading || !cachedContent ? (
            <p className="text-center text-sm text-slate-500">Loading saved content...</p>
          ) : (
            <div className="space-y-4">
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

        {selectedDocuments.length > 0 && (
          <section className="w-full space-y-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold tracking-tight text-slate-900">
                Chat across selected documents
              </h2>
              <div className="flex flex-wrap items-center gap-1.5">
                {selectedDocuments.map((selected) => (
                  <span
                    key={selected.id}
                    className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                  >
                    {selected.original_filename}
                    <button
                      type="button"
                      onClick={() => handleToggleSelect(selected)}
                      aria-label={`Remove ${selected.original_filename} from chat`}
                      className="text-slate-400 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Keyed by the sorted selection so adding/removing any
                document starts a fresh conversation — the same
                predictable "changing what you're chatting with resets
                the chat" rule as before, just generalized from "switch
                document" to "change the selection". */}
            <ChatPanel
              key={`chat-${selectedDocuments
                .map((selected) => selected.id)
                .sort()
                .join(",")}`}
              documents={selectedDocuments}
            />
          </section>
        )}
      </div>
    </main>
  );
}

export default HomePage;
