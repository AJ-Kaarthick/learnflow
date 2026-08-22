import { useEffect, useRef, useState } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { generateMindMap } from "../api/mindmap";
import { treeToMarkdown } from "../utils/treeToMarkdown";
import { downloadTextFile } from "../utils/downloadFile";

// Reused across renders rather than constructed per-call — Markmap's
// own docs note the Transformer holds parser state that's fine (and
// cheaper) to share.
const transformer = new Transformer();

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

function MindMapPanel({ documentId, initialMindmap = null, onGenerated }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [structure, setStructure] = useState(initialMindmap?.structure ?? null);
  const [errorMessage, setErrorMessage] = useState("");
  const [downloadState, setDownloadState] = useState("idle"); // idle | downloaded

  const svgRef = useRef(null);
  const markmapRef = useRef(null);

  async function handleGenerate() {
    setStatus("loading");
    setErrorMessage("");
    try {
      const result = await generateMindMap(documentId);
      setStructure(result.structure);
      // See SummaryPanel's onGenerated call for why this is needed:
      // keeps StudyPage's cachedContent (the single source of truth
      // panels remount from on tab switch) in sync with what was just
      // generated. Passed as the same { structure } shape
      // getMindMap/generateMindMap both already return and
      // initialMindmap already expects — no new shape introduced.
      onGenerated?.(result);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  // Renders (or re-renders) into the SVG whenever a new tree arrives.
  useEffect(() => {
    if (!structure || !svgRef.current) return;

    const markdown = treeToMarkdown(structure);
    const { root } = transformer.transform(markdown);

    if (!markmapRef.current) {
      markmapRef.current = Markmap.create(svgRef.current, undefined, root);
    } else {
      markmapRef.current.setData(root);
      markmapRef.current.fit();
    }
  }, [structure]);

  function handleDownload() {
    if (!structure) return;
    downloadTextFile("mindmap.md", treeToMarkdown(structure));
    setDownloadState("downloaded");
    setTimeout(() => setDownloadState("idle"), 2000);
  }

  const isLoading = status === "loading";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Mind Map</h2>
        <div className="flex flex-wrap items-center gap-2">
          {structure && (
            <button onClick={handleDownload} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
              {downloadState === "downloaded" ? "Downloaded!" : "Download"}
            </button>
          )}
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
          >
            {isLoading && (
              <span
                className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
                aria-hidden="true"
              />
            )}
            {isLoading ? "Generating..." : "Generate mind map"}
          </button>
        </div>
      </div>

      {status === "idle" && !structure && (
        <p className="text-sm text-slate-500">
          Create a visual mind map of this document's key ideas.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {structure && (
        <svg
          ref={svgRef}
          className="h-[320px] w-full rounded-md border border-slate-200 bg-white sm:h-[420px]"
        />
      )}
    </div>
  );
}

export default MindMapPanel;
