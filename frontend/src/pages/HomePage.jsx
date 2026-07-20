import { useState } from "react";
import BackendStatus from "../components/BackendStatus";
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

function HomePage() {
  const [document, setDocument] = useState(null);

  const extractedVeryLittleText =
    document && document.status === "ready" && document.character_count < 50;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Learn<span className="text-accent-600">Flow</span>
          </h1>
          <p className="mt-1 text-sm text-slate-500">Upload a PDF to get started</p>
        </header>

        <section className="mx-auto w-full max-w-xl space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <BackendStatus />

          <UploadForm onUploadComplete={setDocument} />

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

        {document && document.status === "ready" && (
          <div className="space-y-4">
            <SummaryPanel key={`summary-${document.id}`} documentId={document.id} />
            <FlashcardsPanel key={`flashcards-${document.id}`} documentId={document.id} />
            <QuizPanel key={`quiz-${document.id}`} documentId={document.id} />
            <MindMapPanel key={`mindmap-${document.id}`} documentId={document.id} />
          </div>
        )}
      </div>
    </main>
  );
}

export default HomePage;
