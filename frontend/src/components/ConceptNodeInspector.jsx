import React from "react";
import ExpandableText from "./ExpandableText.jsx";
import { getCitationsForNode } from "../utils/visualizeState.js";

function ConceptNodeInspector({
  selectedNode,
  connectedEdges = [],
  allNodes = [],
  citations = [],
  documentLookup = {},
  onSelectNode,
  onClose,
}) {
  if (!selectedNode) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-slate-500">
        <svg
          className="mb-3 h-10 w-10 text-slate-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-sm font-medium text-slate-700">No Concept Selected</p>
        <p className="mt-1 text-xs text-slate-500">
          Click any concept node in the network to inspect its definition, connections, and source citations.
        </p>
      </div>
    );
  }

  const nodeMap = new Map((allNodes || []).map((n) => [n.id, n]));
  const nodeCitations = getCitationsForNode(selectedNode.id, citations);

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-surface p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-200 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
            <span className="inline-flex items-center rounded-full bg-accent-100 px-2.5 py-0.5 text-xs font-semibold text-accent-800">
              {selectedNode.category || "General"}
            </span>
            {selectedNode.importance && (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                Weight: {selectedNode.importance.toFixed(1)}x
              </span>
            )}
          </div>
          <h3 className="text-base font-bold text-slate-900 leading-tight">
            {selectedNode.label}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          aria-label="Close inspector"
        >
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>

      {/* Summary / Definition */}
      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Definition</h4>
        <p className="mt-1 text-sm leading-relaxed text-slate-700">
          {selectedNode.summary || "No definition provided."}
        </p>
      </div>

      {/* Contributing Documents */}
      {selectedNode.document_ids && selectedNode.document_ids.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Source Documents</h4>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {selectedNode.document_ids.map((docId) => {
              const docName = documentLookup[docId] || "Document";
              return (
                <span
                  key={docId}
                  className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  <svg className="h-3 w-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span className="truncate max-w-[180px]">{docName}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Connected Concepts */}
      <div className="mt-5 border-t border-slate-100 pt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Connected Concepts ({connectedEdges.length})
        </h4>
        {connectedEdges.length === 0 ? (
          <p className="mt-1 text-xs italic text-slate-400">Isolated concept with no direct connections.</p>
        ) : (
          <div className="mt-2 space-y-2">
            {connectedEdges.map((edge) => {
              const isOutgoing = edge.source === selectedNode.id;
              const neighborId = isOutgoing ? edge.target : edge.source;
              const neighbor = nodeMap.get(neighborId);

              if (!neighbor) return null;

              return (
                <div
                  key={edge.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-2 text-xs hover:bg-slate-100 transition"
                >
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="rounded bg-accent-100 px-1.5 py-0.5 text-[10px] font-medium text-accent-800 shrink-0">
                      {edge.label || "relates to"}
                    </span>
                    <span className="text-slate-400">{isOutgoing ? "→" : "←"}</span>
                    <span className="font-medium text-slate-800 truncate">{neighbor.label}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSelectNode && onSelectNode(neighbor)}
                    className="shrink-0 text-xs font-medium text-accent-700 hover:text-accent-800 hover:underline"
                  >
                    Focus
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Grounded Source Citations */}
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Grounded Excerpts ({nodeCitations.length})
          </h4>
        </div>
        {nodeCitations.length === 0 ? (
          <p className="mt-1 text-xs italic text-slate-400">
            No direct chunk citations extracted for this concept.
          </p>
        ) : (
          <div className="mt-2 space-y-3">
            {nodeCitations.map((citation, index) => {
              const relevance = citation.score ? `${Math.round(citation.score * 100)}% match` : null;
              return (
                <div
                  key={citation.chunk_id || index}
                  className="rounded-lg border border-slate-200 bg-surface p-3 shadow-xs"
                >
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-700 truncate">
                      <svg className="h-3 w-3 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                        <path
                          fillRule="evenodd"
                          d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="truncate">{citation.document_name || "Document"}</span>
                    </span>
                    {relevance && (
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 shrink-0">
                        {relevance}
                      </span>
                    )}
                  </div>
                  <ExpandableText
                    text={citation.content}
                    textClassName="text-slate-600 text-xs italic leading-relaxed"
                    fadeFromClassName="from-surface"
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConceptNodeInspector;
