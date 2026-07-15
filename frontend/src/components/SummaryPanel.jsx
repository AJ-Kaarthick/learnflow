import { useState } from "react";
import { generateSummary } from "../api/summary";

function SummaryPanel({ documentId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleGenerate() {
    setStatus("loading");
    setErrorMessage("");
    try {
      const result = await generateSummary(documentId);
      setSummary(result);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  const isLoading = status === "loading";

  return (
    <div className="border-t border-slate-200 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-900">Summary</h2>
        <button
          onClick={handleGenerate}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          {isLoading && (
            <span
              className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
              aria-hidden="true"
            />
          )}
          {isLoading ? "Generating..." : "Generate summary"}
        </button>
      </div>

      {status === "idle" && !summary && (
        <p className="text-sm text-slate-500">
          Generate a short, structured summary of this document.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {summary && <p className="text-sm text-slate-700 whitespace-pre-wrap">{summary.content}</p>}
    </div>
  );
}

export default SummaryPanel;
