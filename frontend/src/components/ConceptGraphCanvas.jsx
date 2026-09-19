import React, { useRef, useState, useMemo } from "react";
import { getConnectedEdgesAndNeighbors } from "../utils/visualizeState.js";

// Category color palettes for clear visual clustering
const CATEGORY_COLORS = [
  { fill: "#e0e7ff", stroke: "#6366f1", text: "#3730a3", badge: "#4f46e5" }, // Indigo
  { fill: "#dcfce7", stroke: "#22c55e", text: "#166534", badge: "#15803d" }, // Emerald
  { fill: "#fef3c7", stroke: "#f59e0b", text: "#92400e", badge: "#b45309" }, // Amber
  { fill: "#e0f2fe", stroke: "#0ea5e9", text: "#075985", badge: "#0369a1" }, // Sky
  { fill: "#f3e8ff", stroke: "#a855f7", text: "#6b21a8", badge: "#7e22ce" }, // Purple
  { fill: "#ffe4e6", stroke: "#f43f5e", text: "#9f1239", badge: "#be123c" }, // Rose
  { fill: "#f1f5f9", stroke: "#64748b", text: "#334155", badge: "#475569" }, // Slate
];

function getCategoryTheme(category, categoryList = []) {
  if (!category) return CATEGORY_COLORS[0];
  const index = categoryList.indexOf(category);
  if (index >= 0) {
    return CATEGORY_COLORS[index % CATEGORY_COLORS.length];
  }
  // Fallback hash
  let hash = 0;
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colorIdx = Math.abs(hash) % CATEGORY_COLORS.length;
  return CATEGORY_COLORS[colorIdx];
}

function ConceptGraphCanvas({
  nodes = [],
  edges = [],
  selectedNodeId = null,
  onSelectNode,
  width = 800,
  height = 600,
}) {
  const svgRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Fast node lookup
  const nodeMap = useMemo(() => {
    const map = new Map();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  // Unique categories for distinct colors
  const categoryList = useMemo(() => {
    const set = new Set();
    nodes.forEach((n) => n.category && set.add(n.category));
    return Array.from(set).sort();
  }, [nodes]);

  // Connected neighbors of the selected node
  const { neighborNodeIds, connectedEdges } = useMemo(() => {
    if (!selectedNodeId) {
      return { neighborNodeIds: new Set(), connectedEdges: [] };
    }
    return getConnectedEdgesAndNeighbors(selectedNodeId, edges);
  }, [selectedNodeId, edges]);

  const connectedEdgeSet = useMemo(() => {
    return new Set(connectedEdges.map((e) => e.id));
  }, [connectedEdges]);

  // Mouse pan handlers
  const handleMouseDown = (e) => {
    if (e.target.tagName === "svg" || e.target.id === "graph-background") {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    setZoom((prev) => Math.min(2.5, Math.max(0.4, prev + delta)));
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleZoomIn = () => setZoom((prev) => Math.min(2.5, prev + 0.15));
  const handleZoomOut = () => setZoom((prev) => Math.max(0.4, prev - 0.15));

  return (
    <div
      className="relative flex-1 h-full w-full select-none overflow-hidden bg-slate-50 border border-slate-200 rounded-xl"
      role="region"
      aria-label="Interactive concept network graph canvas"
    >
      {/* Canvas SVG */}
      <svg
        ref={svgRef}
        className={`h-full w-full ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        viewBox={`0 0 ${width} ${height}`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        onClick={(e) => {
          if (e.target.id === "graph-background") {
            onSelectNode && onSelectNode(null);
          }
        }}
      >
        <defs>
          {/* Arrow marker for edges */}
          <marker
            id="concept-arrow"
            viewBox="0 0 10 10"
            refX="22"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#94a3b8" />
          </marker>
          <marker
            id="concept-arrow-active"
            viewBox="0 0 10 10"
            refX="22"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#4f46e5" />
          </marker>

          {/* Dot pattern background */}
          <pattern id="graph-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1" fill="#cbd5e1" />
          </pattern>
        </defs>

        {/* Background Clickable Area */}
        <rect
          id="graph-background"
          x="-5000"
          y="-5000"
          width="10000"
          height="10000"
          fill="url(#graph-grid)"
        />

        {/* Pan and Zoom Layer */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges Layer */}
          <g className="edges-layer">
            {edges.map((edge) => {
              const sourceNode = nodeMap.get(edge.source);
              const targetNode = nodeMap.get(edge.target);

              if (!sourceNode || !targetNode) return null;

              const isEdgeConnected = connectedEdgeSet.has(edge.id);
              const isDimmed = selectedNodeId && !isEdgeConnected;

              const midX = (sourceNode.x + targetNode.x) / 2;
              const midY = (sourceNode.y + targetNode.y) / 2;

              return (
                <g
                  key={edge.id}
                  className="edge-group transition-opacity duration-200"
                  opacity={isDimmed ? 0.2 : 1.0}
                >
                  {/* Line */}
                  <line
                    x1={sourceNode.x}
                    y1={sourceNode.y}
                    x2={targetNode.x}
                    y2={targetNode.y}
                    stroke={isEdgeConnected ? "#4f46e5" : "#94a3b8"}
                    strokeWidth={isEdgeConnected ? 2.5 : 1.5}
                    strokeDasharray={isEdgeConnected ? undefined : "4,2"}
                    markerEnd={isEdgeConnected ? "url(#concept-arrow-active)" : "url(#concept-arrow)"}
                  />

                  {/* Relationship Label Pill */}
                  {edge.label && (
                    <g transform={`translate(${midX}, ${midY})`}>
                      <rect
                        x="-30"
                        y="-9"
                        width="60"
                        height="18"
                        rx="9"
                        fill="#ffffff"
                        stroke={isEdgeConnected ? "#c7d2fe" : "#e2e8f0"}
                        strokeWidth="1"
                        className="shadow-xs"
                      />
                      <text
                        textAnchor="middle"
                        dy="3.5"
                        fontSize="9"
                        fontWeight="600"
                        fill={isEdgeConnected ? "#4338ca" : "#64748b"}
                      >
                        {edge.label.length > 10 ? `${edge.label.slice(0, 9)}…` : edge.label}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>

          {/* Nodes Layer */}
          <g className="nodes-layer">
            {nodes.map((node) => {
              const isSelected = selectedNodeId === node.id;
              const isNeighbor = neighborNodeIds.has(node.id);
              const isDimmed = selectedNodeId && !isSelected && !isNeighbor;
              const theme = getCategoryTheme(node.category, categoryList);
              const r = node.radius || 26;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="node-group cursor-pointer transition-opacity duration-200 focus:outline-hidden"
                  tabIndex={0}
                  role="button"
                  aria-label={`${node.label}, Category: ${node.category || "General"}`}
                  aria-pressed={isSelected}
                  opacity={isDimmed ? 0.28 : 1.0}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectNode && onSelectNode(node);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectNode && onSelectNode(node);
                    }
                  }}
                >
                  {/* Active focus outer ring */}
                  {isSelected && (
                    <circle
                      r={r + 8}
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth="2.5"
                      strokeDasharray="4,3"
                      className="animate-spin-slow"
                    />
                  )}

                  {/* Node Circle */}
                  <circle
                    r={r}
                    fill={isSelected ? "#4f46e5" : theme.fill}
                    stroke={isSelected ? "#312e81" : theme.stroke}
                    strokeWidth={isSelected ? 3 : 2}
                    className="transition-all duration-150 filter drop-shadow-sm hover:brightness-95"
                  />

                  {/* Multi-document indicator dot if shared across >=2 docs */}
                  {node.document_ids && node.document_ids.length > 1 && (
                    <circle
                      cx={r * 0.7}
                      cy={-r * 0.7}
                      r="4.5"
                      fill="#ec4899"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                  )}

                  {/* Central Icon or Initials */}
                  <text
                    textAnchor="middle"
                    dy="4"
                    fontSize={Math.max(10, r * 0.42)}
                    fontWeight="bold"
                    fill={isSelected ? "#ffffff" : theme.text}
                    pointerEvents="none"
                  >
                    {node.label ? node.label.slice(0, 2).toUpperCase() : "•"}
                  </text>

                  {/* Text Label Pill below node */}
                  <g transform={`translate(0, ${r + 14})`}>
                    <rect
                      x="-55"
                      y="-9"
                      width="110"
                      height="18"
                      rx="4"
                      fill={isSelected ? "#312e81" : "#ffffff"}
                      stroke={isSelected ? "#4f46e5" : "#cbd5e1"}
                      strokeWidth={isSelected ? 1.5 : 1}
                      className="shadow-xs"
                      opacity="0.95"
                    />
                    <text
                      textAnchor="middle"
                      dy="3.5"
                      fontSize="10"
                      fontWeight={isSelected ? "700" : "500"}
                      fill={isSelected ? "#ffffff" : "#1e293b"}
                      pointerEvents="none"
                    >
                      {node.label.length > 18 ? `${node.label.slice(0, 16)}…` : node.label}
                    </text>
                  </g>
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {/* Floating Canvas Navigation Toolbar */}
      <div className="absolute top-3 right-3 flex items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 shadow-sm backdrop-blur-xs">
        <button
          type="button"
          onClick={handleZoomIn}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100 transition"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100 transition"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <button
          type="button"
          onClick={resetView}
          className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 transition"
          title="Reset View"
          aria-label="Reset View"
        >
          Reset
        </button>
      </div>

      {/* Floating Canvas Legend */}
      <div className="absolute bottom-3 left-3 hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-white/90 px-3 py-1.5 text-[11px] text-slate-600 shadow-xs backdrop-blur-xs">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-indigo-500" />
          Single-Doc
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-pink-500" />
          Cross-Document Concept
        </span>
        <span className="text-slate-300">|</span>
        <span className="text-slate-400">Scroll to zoom • Drag to pan</span>
      </div>
    </div>
  );
}

export default ConceptGraphCanvas;
