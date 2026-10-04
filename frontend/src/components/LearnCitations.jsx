import { useState } from "react";
import ExpandableText from "./ExpandableText.jsx";

function LearnCitations({ sources = [] }) {
  const [isOpen, setIsOpen] = useState(true);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 rounded"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-700">
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-4 w-4 text-accent-600"
            aria-hidden="true"
          >
            <path d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2Zm0 13a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 15Zm0-6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM5 9.25a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 5 9.25Zm7.75 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1-.75-.75Z" />
          </svg>
          Source Grounding & Citations ({sources.length})
        </span>
        <span className="text-xs text-slate-400">
          {isOpen ? "Hide" : "Show"}
        </span>
      </button>

      {isOpen && (
        <div className="mt-3 space-y-2.5">
          {sources.map((source, index) => {
            const scorePercent =
              typeof source.score === "number" && !isNaN(source.score)
                ? `${Math.round(source.score * 100)}%`
                : null;

            return (
              <div
                key={source.chunk_id || `source-${index}`}
                className="rounded-lg border border-slate-200/80 bg-surface p-3 text-xs shadow-xs"
              >
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800">
                    <svg
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="h-3 w-3 text-slate-500"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M4.5 2A1.5 1.5 0 0 0 3 3.5v13A1.5 1.5 0 0 0 4.5 18h11a1.5 1.5 0 0 0 1.5-1.5V7.621a1.5 1.5 0 0 0-.44-1.06l-4.12-4.122A1.5 1.5 0 0 0 11.378 2H4.5Zm4.75 6.75a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5H10a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h5a.75.75 0 0 1 0 1.5H10a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h5a.75.75 0 0 1 0 1.5H10a.75.75 0 0 1-.75-.75Z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {source.document_name || "Document"}
                  </span>
                  {scorePercent && (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                      Relevance: {scorePercent}
                    </span>
                  )}
                </div>

                <ExpandableText
                  text={source.content}
                  textClassName="text-slate-600 text-xs italic leading-relaxed"
                  fadeFromClassName="from-surface"
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default LearnCitations;
