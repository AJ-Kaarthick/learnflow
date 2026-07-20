import { useState } from "react";
import { generateFlashcards } from "../api/flashcards";

function FlashcardsPanel({ documentId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [flashcards, setFlashcards] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [flippedIds, setFlippedIds] = useState(new Set());

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

  const isLoading = status === "loading";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Flashcards</h2>
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

      {status === "idle" && flashcards.length === 0 && (
        <p className="text-sm text-slate-500">
          Create a set of flashcards to test yourself on this document's key concepts.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {flashcards.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
