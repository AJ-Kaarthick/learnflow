import { useState } from "react";
import { generateFlashcards } from "../api/flashcards";
import { downloadTextFile } from "../utils/downloadFile";
import { flashcardsToMarkdown } from "../utils/markdownExport";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40";

function flashcardsToText(flashcards) {
  return flashcards.map((card) => `Q: ${card.question}\nA: ${card.answer}`).join("\n\n");
}

function FlashcardsPanel({ documentId, initialFlashcards = [] }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [flashcards, setFlashcards] = useState(initialFlashcards);
  const [errorMessage, setErrorMessage] = useState("");
  const [flippedIds, setFlippedIds] = useState(new Set());
  const [copyState, setCopyState] = useState("idle"); // idle | copied
  const [downloadState, setDownloadState] = useState("idle"); // idle | downloaded

  async function handleGenerate() {
    setStatus("loading");
    setErrorMessage("");
    try {
      const cards = await generateFlashcards(documentId);
      setFlashcards(cards);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  function toggleFlip(cardId) {
    setFlippedIds((previous) => {
      const next = new Set(previous);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  }

  async function handleCopy() {
    if (flashcards.length === 0) return;
    try {
      await navigator.clipboard.writeText(flashcardsToText(flashcards));
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      // Clipboard access can fail (permissions, insecure context); no
      // crash, just stays in its normal state.
    }
  }

  function handleDownload() {
    if (flashcards.length === 0) return;
    downloadTextFile("flashcards.md", flashcardsToMarkdown(flashcards));
    setDownloadState("downloaded");
    setTimeout(() => setDownloadState("idle"), 2000);
  }

  const isLoading = status === "loading";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Flashcards</h2>
        <div className="flex flex-wrap items-center gap-2">
          {flashcards.length > 0 && (
            <>
              <button onClick={handleCopy} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
                {copyState === "copied" ? "Copied!" : "Copy"}
              </button>
              <button onClick={handleDownload} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
                {downloadState === "downloaded" ? "Downloaded!" : "Download"}
              </button>
            </>
          )}
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:opacity-40"
          >
            {isLoading && (
              <span
                className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
                aria-hidden="true"
              />
            )}
            {isLoading ? "Generating..." : "Generate flashcards"}
          </button>
        </div>
      </div>

      {status === "idle" && flashcards.length === 0 && (
        <p className="text-sm text-slate-500">
          Create a set of flashcards to test yourself on this document's key concepts.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {flashcards.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {flashcards.map((card) => {
            const isFlipped = flippedIds.has(card.id);
            return (
              <button
                key={card.id}
                type="button"
                onClick={() => toggleFlip(card.id)}
                disabled={isLoading}
                className="text-left rounded-lg border border-slate-200 p-3 transition-colors hover:border-accent-300 hover:bg-accent-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-accent-700">
                    {isFlipped ? "Answer" : "Question"}
                  </p>
                  <span className="text-[10px] text-slate-400">Tap to flip</span>
                </div>
                <p className="mt-1 text-sm text-slate-800">
                  {isFlipped ? card.answer : card.question}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default FlashcardsPanel;
