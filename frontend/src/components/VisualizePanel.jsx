import React, { useMemo, useState } from "react";
import { generateVisualizeGraph } from "../api/visualize.js";
import { isGuestLimitError } from "../api/errors.js";
import GuestLimitNotice from "./GuestLimitNotice.jsx";
import ConceptGraphCanvas from "./ConceptGraphCanvas.jsx";
import ConceptNodeInspector from "./ConceptNodeInspector.jsx";
import {
  computeGraphLayout,
  filterGraphByCategory,
  getConnectedEdgesAndNeighbors,
  getGraphCategories,
  isGraphStale,
} from "../utils/visualizeState.js";

const VISUALIZE_DEPTHS = [
  { id: "overview", label: "Overview", desc: "Core high-level concepts (max 10)" },
  { id: "standard", label: "Standard", desc: "Balanced concept network (max 16)" },
  { id: "in-depth", label: "In-Depth", desc: "Detailed comprehensive graph (max 22)" },
];

function VisualizePanel({
  selectedDocuments = [],
  session = {},
  onUpdateSession,
  isNoneReadable = false,
}) {
  const [activeDepth, setActiveDepth] = useState(session.depth || "standard");
  const [activeCategory, setActiveCategory] = useState("all");
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const graph = session.graph || null;
  const fullDocumentIds = selectedDocuments.map((d) => d.id);

  // Document name lookup
  const documentLookup = useMemo(() => {
    const map = {};
    selectedDocuments.forEach((doc) => {
      map[doc.id] = doc.original_filename;
    });
    return map;
  }, [selectedDocuments]);

  // Check if current document selection is stale relative to generated graph
  const isStale = useMemo(() => {
    if (!graph?.grounding_metadata?.document_ids) return false;
    return isGraphStale(fullDocumentIds, graph.grounding_metadata.document_ids);
  }, [fullDocumentIds, graph]);

  // Compute graph layout once when graph changes
  const layoutNodes = useMemo(() => {
    if (!graph?.nodes || graph.nodes.length === 0) return [];
    return computeGraphLayout(graph.nodes, graph.edges || [], 800, 600, 45);
  }, [graph]);

  // Categories present in the graph
  const categories = useMemo(() => {
    return getGraphCategories(graph?.nodes || []);
  }, [graph?.nodes]);

  // Filter nodes and edges by active category
  const { filteredNodes, filteredEdges } = useMemo(() => {
    return filterGraphByCategory(layoutNodes, graph?.edges || [], activeCategory);
  }, [layoutNodes, graph?.edges, activeCategory]);

  // Currently selected node object
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return layoutNodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, layoutNodes]);

  // Connected edges for the selected node
  const { connectedEdges } = useMemo(() => {
    if (!selectedNodeId || !graph?.edges) return { connectedEdges: [] };
    return getConnectedEdgesAndNeighbors(selectedNodeId, graph.edges);
  }, [selectedNodeId, graph?.edges]);

  // Generate / Regenerate graph handler
  const handleGenerateGraph = async () => {
    if (isNoneReadable || fullDocumentIds.length === 0) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await generateVisualizeGraph({
        documentIds: fullDocumentIds,
        depth: activeDepth,
      });

      onUpdateSession &&
        onUpdateSession({
          graph: result,
          depth: activeDepth,
        });

      // Select first node by default if available
      if (result.nodes && result.nodes.length > 0) {
        setSelectedNodeId(result.nodes[0].id);
      } else {
        setSelectedNodeId(null);
      }
      setActiveCategory("all");
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col space-y-4">
      {/* Error & Quota Banner */}
      {error && isGuestLimitError(error) ? (
        <GuestLimitNotice error={error} />
      ) : error ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800 flex items-center justify-between"
          role="alert"
        >
          <span>{error.message || "Visualization failed"}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-red-600 hover:text-red-800 font-bold"
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      ) : null}

      {/* Stale Document Selection Warning */}
      {graph && isStale && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900 shadow-2xs"
          role="status"
        >
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 shrink-0 text-amber-600" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                clipRule="evenodd"
              />
            </svg>
            <span>The selected study documents have changed since this visualization was generated.</span>
          </div>
          <button
            type="button"
            disabled={isLoading || isNoneReadable}
            onClick={handleGenerateGraph}
            className="rounded bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white transition-colors hover:bg-amber-700 disabled:opacity-50"
          >
            Update Visualization
          </button>
        </div>
      )}

      {/* Initial Hero / Empty State */}
      {!graph && !isLoading && (
        <div className="rounded-xl border border-slate-200 bg-surface p-6 shadow-xs sm:p-8">
          <div className="mx-auto max-w-xl text-center space-y-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-100 text-accent-700">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="h-6 w-6">
                <circle cx="12" cy="12" r="3" />
                <circle cx="4" cy="6" r="2" />
                <circle cx="20" cy="6" r="2" />
                <circle cx="6" cy="18" r="2" />
                <circle cx="18" cy="18" r="2" />
                <path d="M6 6l4 4m4 0l4-4M6 18l4-4m4 0l4 4" />
              </svg>
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-900">Interactive Concept Network</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Visualize Mode analyzes your selected study material to build an interactive concept graph.
                Explore relationships, connected dependencies, and grounded source citations.
              </p>
            </div>

            {/* Depth Selector */}
            <div className="flex items-center justify-center gap-2 pt-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Graph Depth:
              </span>
              <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
                {VISUALIZE_DEPTHS.map((depth) => (
                  <button
                    key={depth.id}
                    type="button"
                    disabled={isLoading}
                    onClick={() => setActiveDepth(depth.id)}
                    className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                      activeDepth === depth.id
                        ? "bg-surface text-slate-900 shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {depth.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-3">
              <button
                type="button"
                disabled={isLoading || isNoneReadable}
                onClick={handleGenerateGraph}
                className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Generate Concept Graph
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="flex flex-1 min-h-[450px] flex-col items-center justify-center rounded-xl border border-slate-200 bg-surface p-8 shadow-xs">
          <div className="h-10 w-10 animate-spin rounded-full border-3 border-accent-200 border-t-accent-600 mb-3" />
          <p className="text-sm font-semibold text-slate-800">Synthesizing Concept Network...</p>
          <p className="mt-1 text-xs text-slate-500 max-w-sm text-center">
            Extracting core concepts, cross-document relations, and grounded citations across your study material.
          </p>
        </div>
      )}

      {/* Active Graph Interactive View */}
      {graph && !isLoading && (
        <div className="flex flex-1 flex-col space-y-3 min-h-[500px]">
          {/* Top Control Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-surface px-4 py-3 shadow-xs">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 truncate">
                  {graph.title || "Concept Network"}
                </h3>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 shrink-0">
                  {graph.nodes?.length || 0} nodes • {graph.edges?.length || 0} edges
                </span>
              </div>
              {graph.summary && (
                <p className="mt-0.5 text-xs text-slate-500 line-clamp-1">{graph.summary}</p>
              )}
            </div>

            {/* Depth & Action Controls */}
            <div className="flex items-center gap-2">
              <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
                {VISUALIZE_DEPTHS.map((depth) => (
                  <button
                    key={depth.id}
                    type="button"
                    disabled={isLoading}
                    onClick={() => {
                      setActiveDepth(depth.id);
                    }}
                    className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                      activeDepth === depth.id
                        ? "bg-surface text-slate-900 shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {depth.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                disabled={isLoading || isNoneReadable}
                onClick={handleGenerateGraph}
                className="rounded-lg bg-accent-50 px-2.5 py-1 text-xs font-semibold text-accent-700 hover:bg-accent-100 transition"
              >
                Regenerate
              </button>
            </div>
          </div>

          {/* Category Filter Chips Bar */}
          {categories.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
              <span className="text-[11px] font-medium text-slate-500 mr-1 shrink-0">Categories:</span>
              <button
                type="button"
                onClick={() => setActiveCategory("all")}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition shrink-0 ${
                  activeCategory === "all"
                    ? "bg-accent-600 text-white"
                    : "border border-slate-200 bg-surface text-slate-700 hover:bg-slate-100"
                }`}
              >
                All ({layoutNodes.length})
              </button>
              {categories.map((cat) => {
                const count = layoutNodes.filter((n) => n.category === cat).length;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setActiveCategory(cat)}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition shrink-0 ${
                      activeCategory === cat
                        ? "bg-accent-600 text-white"
                        : "border border-slate-200 bg-surface text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {cat} ({count})
                  </button>
                );
              })}
            </div>
          )}

          {/* Main 2-Column Split: Graph Canvas (left) and Concept Inspector (right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-[460px]">
            {/* Graph Canvas Column */}
            <div className="lg:col-span-8 flex flex-col h-full min-h-[420px]">
              <ConceptGraphCanvas
                nodes={filteredNodes}
                edges={filteredEdges}
                selectedNodeId={selectedNodeId}
                onSelectNode={(node) => setSelectedNodeId(node ? node.id : null)}
              />
            </div>

            {/* Concept Node Inspector Column */}
            <div className="lg:col-span-4 flex flex-col h-full min-h-[420px] rounded-xl border border-slate-200 bg-surface overflow-hidden shadow-xs">
              <ConceptNodeInspector
                selectedNode={selectedNode}
                connectedEdges={connectedEdges}
                allNodes={layoutNodes}
                citations={graph.citations || []}
                documentLookup={documentLookup}
                onSelectNode={(node) => setSelectedNodeId(node ? node.id : null)}
                onClose={() => setSelectedNodeId(null)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VisualizePanel;
