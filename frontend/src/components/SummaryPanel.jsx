import { useState } from "react";
import { generateSummary } from "../api/summary";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40";

function SummaryPanel({ documentId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [copyState, setCopyState] = useState("idle"); // idle | copied
  const [downloadState, setDownloadState] = useState("idle"); // idle | downloaded

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

  async function handleCopy() {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summary.content);
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      // Clipboard access can fail (permissions, insecure context); no
      // crash, just stays in its normal state.
    }
  }

  function handleDownload() {
    if (!summary) return;
    const blob = new Blob([summary.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "summary.txt";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setDownloadState("downloaded");
    setTimeout(() => setDownloadState("idle"), 2000);
  }

  const isLoading = status === "loading";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Summary</h2>
        <div className="flex flex-wrap items-center gap-2">
          {summary && (
            <>
              <button onClick={handleCopy} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
                {copyState === "copied" ? "Copied!" : "Copy"}
              </button>
              <button
                onClick={handleDownload}
                disabled={isLoading}
                className={SECONDARY_BUTTON_CLASSES}
              >
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
            {isLoading ? "Generating..." : "Generate summary"}
          </button>
        </div>
      </div>

      {status === "idle" && !summary && (
        <p className="text-sm text-slate-500">
          Generate a short, structured summary of this document.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {summary && <p className="text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">{summary.content}</p>}
    </div>
  );
}

export default SummaryPanel;
