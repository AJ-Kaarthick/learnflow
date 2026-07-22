import { useEffect, useState } from "react";
import { deleteDocument, listDocuments, renameDocument } from "../api/documents";
import { getFlashcards } from "../api/flashcards";
import { getMindMap } from "../api/mindmap";
import { getQuiz } from "../api/quiz";
import { getSummary } from "../api/summary";
import BackendStatus from "../components/BackendStatus";
import DocumentList from "../components/DocumentList";
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
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);

  const [document, setDocument] = useState(null);
  const [cachedContent, setCachedContent] = useState(null);
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(() => {
    refreshDocumentList();
  }, []);

  async function refreshDocumentList() {
    setDocumentsLoading(true);
    try {
      const list = await listDocuments();
      setDocuments(list);
    } catch {
      // Leave the list as-is; the section just shows whatever it had.
    } finally {
      setDocumentsLoading(false);
    }
  }

  async function openDocument(doc) {
    setDocument(doc);
    setCachedContent(null);
    if (doc.status !== "ready") return;
    setContentLoading(true);
    const content = await loadCachedContent(doc.id);
    setCachedContent(content);
    setContentLoading(false);
  }

  async function handleUploadComplete(newDocument) {
    await refreshDocumentList();
    await openDocument(newDocument);
  }

  async function handleRename(documentId, newName) {
    const updated = await renameDocument(documentId, newName);
    setDocuments((previous) => previous.map((doc) => (doc.id === documentId ? updated : doc)));
    setDocument((previous) => (previous && previous.id === documentId ? updated : previous));
  }

  async function handleDelete(documentId) {
    await deleteDocument(documentId);
    setDocuments((previous) => previous.filter((doc) => doc.id !== documentId));
    if (document && document.id === documentId) {
      setDocument(null);
      setCachedContent(null);
    }
  }

  const extractedVeryLittleText =
    document && document.status === "ready" && document.character_count < 50;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Learn<span className="text-accent-600">Flow</span>
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick up where you left off, or upload a new PDF.
          </p>
        </header>

        <section className="mx-auto w-full max-w-xl space-y-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">
            Your documents
          </h2>
          {documentsLoading ? (
            <p className="text-sm text-slate-500">Loading documents...</p>
          ) : (
            <DocumentList
              documents={documents}
              activeDocumentId={document?.id ?? null}
              onOpen={openDocument}
              onRename={handleRename}
              onDelete={handleDelete}
            />
          )}
        </section>

        <section className="mx-auto w-full max-w-xl space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
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
                <p className="text-sm text-slate-700 whitespace-pre-wrap">
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
      </div>
    </main>
  );
}

export default HomePage;
