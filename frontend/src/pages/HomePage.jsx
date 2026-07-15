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
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-10">
      <div className="max-w-lg w-full bg-white border border-slate-200 rounded-lg p-8 space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">LearnFlow</h1>
          <p className="mt-1 text-sm text-slate-500">Upload a PDF to get started</p>
        </div>

        <BackendStatus />

        <UploadForm onUploadComplete={setDocument} />

        {document && (
          <div className="border-t border-slate-200 pt-4 space-y-2">
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

        {document && document.status === "ready" && (
          <SummaryPanel key={`summary-${document.id}`} documentId={document.id} />
        )}
        {document && document.status === "ready" && (
          <FlashcardsPanel key={`flashcards-${document.id}`} documentId={document.id} />
        )}
        {document && document.status === "ready" && (
          <QuizPanel key={`quiz-${document.id}`} documentId={document.id} />
        )}
        {document && document.status === "ready" && (
          <MindMapPanel key={`mindmap-${document.id}`} documentId={document.id} />
        )}
      </div>
    </main>
  );
}

export default HomePage;
