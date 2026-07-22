import { useEffect, useRef, useState } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { generateMindMap } from "../api/mindmap";
import { treeToMarkdown } from "../utils/treeToMarkdown";

// Reused across renders rather than constructed per-call — Markmap's
// own docs note the Transformer holds parser state that's fine (and
// cheaper) to share.
const transformer = new Transformer();

function MindMapPanel({ documentId, initialMindmap = null }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [structure, setStructure] = useState(initialMindmap?.structure ?? null);
  const [errorMessage, setErrorMessage] = useState("");

  const svgRef = useRef(null);
  const markmapRef = useRef(null);

  async function handleGenerate() {
    setStatus("loading");
    setErrorMessage("");
    try {
      const result = await generateMindMap(documentId);
      setStructure(result.structure);
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

  const isLoading = status === "loading";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Mind Map</h2>
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
          {isLoading ? "Generating..." : "Generate mind map"}
        </button>
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
          className="h-[320px] w-full rounded-md border border-slate-200 sm:h-[420px]"
        />
      )}
    </div>
  );
}

export default MindMapPanel;
