/**
 * Pure state and layout utility functions for LearnFlow Visualize Mode.
 * Implements native, zero-dependency force relaxation layout and graph querying.
 */

/**
 * Computes deterministic 2D coordinates for concept nodes within a viewBox.
 * Uses an initial circular distribution followed by iterative force relaxation (repulsion + spring attraction + center gravity).
 *
 * @param {Array<{id: string, label: string, importance?: number}>} nodes
 * @param {Array<{id: string, source: string, target: string}>} edges
 * @param {number} width Canvas coordinate width (default 800)
 * @param {number} height Canvas coordinate height (default 600)
 * @param {number} iterations Relaxation iterations (default 50)
 * @returns {Array<{id: string, label: string, x: number, y: number, radius: number, importance: number}>}
 */
export function computeGraphLayout(nodes = [], edges = [], width = 800, height = 600, iterations = 50) {
  if (!nodes || nodes.length === 0) {
    return [];
  }

  const padding = 60;
  const centerX = width / 2;
  const centerY = height / 2;
  const count = nodes.length;

  // 1. Initial circular placement around center with deterministic radius
  const initRadius = Math.min(width, height) * 0.35;
  const layoutNodes = nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    const importance = typeof node.importance === "number" ? Math.max(0.5, Math.min(3, node.importance)) : 1.0;
    const radius = 24 + (importance - 1.0) * 8; // 20px to 40px radius

    return {
      ...node,
      importance,
      radius,
      x: centerX + initRadius * Math.cos(angle),
      y: centerY + initRadius * Math.sin(angle),
      vx: 0,
      vy: 0,
    };
  });

  if (count === 1) {
    layoutNodes[0].x = centerX;
    layoutNodes[0].y = centerY;
    return layoutNodes;
  }

  // Build node lookup by ID
  const nodeMap = new Map();
  layoutNodes.forEach((n) => nodeMap.set(n.id, n));

  // Valid edges
  const validEdges = edges.filter(
    (e) => nodeMap.has(e.source) && nodeMap.has(e.target) && e.source !== e.target
  );

  // 2. Force relaxation iterations
  const idealEdgeLength = 160;
  const repulsionConstant = 18000;
  const springConstant = 0.04;
  const gravityConstant = 0.03;
  const damping = 0.85;

  for (let iter = 0; iter < iterations; iter++) {
    // A. Repulsion between all node pairs (Coulomb-like)
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const u = layoutNodes[i];
        const v = layoutNodes[j];
        const dx = v.x - u.x;
        const dy = v.y - u.y;
        const distSq = dx * dx + dy * dy || 1;
        const dist = Math.sqrt(distSq);

        const force = repulsionConstant / (distSq + 200);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        u.vx -= fx;
        u.vy -= fy;
        v.vx += fx;
        v.vy += fy;
      }
    }

    // B. Spring attraction along edges (Hooke's law)
    for (const edge of validEdges) {
      const u = nodeMap.get(edge.source);
      const v = nodeMap.get(edge.target);
      const dx = v.x - u.x;
      const dy = v.y - u.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const displacement = dist - idealEdgeLength;
      const force = displacement * springConstant;

      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      u.vx += fx;
      u.vy += fy;
      v.vx -= fx;
      v.vy -= fy;
    }

    // C. Center gravity and position integration
    for (const n of layoutNodes) {
      const toCenterX = centerX - n.x;
      const toCenterY = centerY - n.y;
      n.vx += toCenterX * gravityConstant;
      n.vy += toCenterY * gravityConstant;

      n.vx *= damping;
      n.vy *= damping;

      n.x += n.vx;
      n.y += n.vy;

      // Bound within canvas bounds with padding
      n.x = Math.max(padding + n.radius, Math.min(width - padding - n.radius, n.x));
      n.y = Math.max(padding + n.radius, Math.min(height - padding - n.radius, n.y));
    }
  }

  return layoutNodes.map(({ vx, vy, ...rest }) => ({
    ...rest,
    x: Math.round(rest.x * 10) / 10,
    y: Math.round(rest.y * 10) / 10,
  }));
}

/**
 * Returns a list of unique, sorted categories present across the graph nodes.
 */
export function getGraphCategories(nodes = []) {
  if (!nodes) return [];
  const set = new Set();
  nodes.forEach((n) => {
    if (n.category && typeof n.category === "string" && n.category.trim()) {
      set.add(n.category.trim());
    }
  });
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

/**
 * Filters the graph nodes and edges by active category filter.
 * If activeCategory is null or "all", all nodes and edges are returned.
 */
export function filterGraphByCategory(nodes = [], edges = [], activeCategory = null) {
  if (!activeCategory || activeCategory === "all") {
    return { filteredNodes: nodes, filteredEdges: edges };
  }

  const filteredNodes = nodes.filter((n) => n.category === activeCategory);
  const nodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  return { filteredNodes, filteredEdges };
}

/**
 * Finds all connected edges and neighbor node IDs for a given focused node.
 */
export function getConnectedEdgesAndNeighbors(nodeId, edges = []) {
  if (!nodeId || !edges) {
    return { connectedEdges: [], neighborNodeIds: new Set() };
  }

  const connectedEdges = edges.filter((e) => e.source === nodeId || e.target === nodeId);
  const neighborNodeIds = new Set();

  connectedEdges.forEach((e) => {
    if (e.source === nodeId) {
      neighborNodeIds.add(e.target);
    } else {
      neighborNodeIds.add(e.source);
    }
  });

  return { connectedEdges, neighborNodeIds };
}

/**
 * Retrieves citations associated with a specific node.
 */
export function getCitationsForNode(nodeId, citations = []) {
  if (!nodeId || !citations) return [];
  return citations.filter((c) => c.node_id === nodeId);
}

/**
 * Checks if the current document selection differs from the documents represented in the graph.
 */
export function isGraphStale(currentDocIds = [], graphDocIds = []) {
  const currentSorted = [...(currentDocIds || [])].sort();
  const graphSorted = [...(graphDocIds || [])].sort();

  if (currentSorted.length !== graphSorted.length) {
    return true;
  }

  return currentSorted.some((id, idx) => id !== graphSorted[idx]);
}
