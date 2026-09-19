import assert from "node:assert/strict";
import { test } from "node:test";
import {
  computeGraphLayout,
  filterGraphByCategory,
  getCitationsForNode,
  getConnectedEdgesAndNeighbors,
  getGraphCategories,
  isGraphStale,
} from "./visualizeState.js";

test("computeGraphLayout handles empty and single node cases", () => {
  assert.deepEqual(computeGraphLayout([]), []);

  const single = computeGraphLayout([{ id: "n1", label: "Solo" }], [], 800, 600);
  assert.equal(single.length, 1);
  assert.equal(single[0].x, 400);
  assert.equal(single[0].y, 300);
  assert.equal(single[0].radius, 24);
});

test("computeGraphLayout computes coordinates within canvas bounds for multi-node graph", () => {
  const nodes = [
    { id: "n1", label: "Node 1", importance: 2.0 },
    { id: "n2", label: "Node 2", importance: 1.0 },
    { id: "n3", label: "Node 3", importance: 0.5 },
  ];
  const edges = [
    { id: "e1", source: "n1", target: "n2", label: "leads to" },
  ];

  const layout = computeGraphLayout(nodes, edges, 800, 600, 30);
  assert.equal(layout.length, 3);

  layout.forEach((node) => {
    assert(node.x >= 60 && node.x <= 740, `Node ${node.id} x out of bounds: ${node.x}`);
    assert(node.y >= 60 && node.y <= 540, `Node ${node.id} y out of bounds: ${node.y}`);
    assert(typeof node.radius === "number" && node.radius > 0);
  });

  // Check importance scaling
  const n1 = layout.find((n) => n.id === "n1");
  const n2 = layout.find((n) => n.id === "n2");
  const n3 = layout.find((n) => n.id === "n3");
  assert(n1.radius > n2.radius);
  assert(n2.radius > n3.radius);
});

test("getGraphCategories extracts sorted unique categories", () => {
  const nodes = [
    { id: "1", category: "Theory" },
    { id: "2", category: "Architecture" },
    { id: "3", category: "Theory" },
    { id: "4", category: "   " },
    { id: "5" },
  ];

  const categories = getGraphCategories(nodes);
  assert.deepEqual(categories, ["Architecture", "Theory"]);
});

test("filterGraphByCategory filters nodes and isolates disconnected edges", () => {
  const nodes = [
    { id: "n1", category: "Theory" },
    { id: "n2", category: "Theory" },
    { id: "n3", category: "Practice" },
  ];
  const edges = [
    { id: "e1", source: "n1", target: "n2" },
    { id: "e2", source: "n1", target: "n3" },
  ];

  // All categories
  const allResult = filterGraphByCategory(nodes, edges, "all");
  assert.equal(allResult.filteredNodes.length, 3);
  assert.equal(allResult.filteredEdges.length, 2);

  // Filter Theory
  const theoryResult = filterGraphByCategory(nodes, edges, "Theory");
  assert.equal(theoryResult.filteredNodes.length, 2);
  assert.equal(theoryResult.filteredEdges.length, 1);
  assert.equal(theoryResult.filteredEdges[0].id, "e1");
});

test("getConnectedEdgesAndNeighbors returns incident edges and adjacent node IDs", () => {
  const edges = [
    { id: "e1", source: "A", target: "B" },
    { id: "e2", source: "C", target: "A" },
    { id: "e3", source: "D", target: "E" },
  ];

  const { connectedEdges, neighborNodeIds } = getConnectedEdgesAndNeighbors("A", edges);
  assert.equal(connectedEdges.length, 2);
  assert.equal(neighborNodeIds.has("B"), true);
  assert.equal(neighborNodeIds.has("C"), true);
  assert.equal(neighborNodeIds.has("D"), false);
});

test("getCitationsForNode filters citations by node_id", () => {
  const citations = [
    { node_id: "A", chunk_id: "c1", content: "Quote 1" },
    { node_id: "B", chunk_id: "c2", content: "Quote 2" },
    { node_id: "A", chunk_id: "c3", content: "Quote 3" },
  ];

  const aCitations = getCitationsForNode("A", citations);
  assert.equal(aCitations.length, 2);
  assert.equal(aCitations[0].chunk_id, "c1");
  assert.equal(aCitations[1].chunk_id, "c3");

  assert.deepEqual(getCitationsForNode("Z", citations), []);
});

test("isGraphStale accurately compares document id sets", () => {
  assert.equal(isGraphStale(["doc-1", "doc-2"], ["doc-2", "doc-1"]), false);
  assert.equal(isGraphStale(["doc-1"], ["doc-1", "doc-2"]), true);
  assert.equal(isGraphStale(["doc-1", "doc-3"], ["doc-1", "doc-2"]), true);
});
