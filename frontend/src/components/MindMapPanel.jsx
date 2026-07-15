import { useEffect, useRef, useState } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { generateMindMap } from "../api/mindmap";
import { treeToMarkdown } from "../utils/treeToMarkdown";

// Reused across renders rather than constructed per-call — Markmap's
// own docs note the Transformer holds parser state that's fine (and
// cheaper) to share.
const transformer = new Transformer();

function MindMapPanel({ documentId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [structure, setStructure] = useState(null);
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
    <div className="border-t border-slate-200 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-900">Mind Map</h2>
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
          className="w-full border border-slate-200 rounded-md"
          style={{ height: "360px" }}
        />
      )}
    </div>
  );
}

export default MindMapPanel;
