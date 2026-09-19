import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { isGuestLimitError } from "./errors.js";
import { generateVisualizeGraph } from "./visualize.js";

let originalFetch;
let calls;

beforeEach(() => {
  originalFetch = globalThis.fetch;
  calls = [];
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function stubFetchOnce(status, body) {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  };
}

test("generateVisualizeGraph sends POST with correct body and credentials", async () => {
  const mockGraph = {
    title: "Operating Systems Concept Network",
    summary: "Key concepts",
    nodes: [
      { id: "node_1", label: "Process Sync", summary: "Sync", category: "Core", document_ids: ["doc-1"], importance: 1.5 },
    ],
    edges: [],
    citations: [],
    grounding_metadata: {
      document_ids: ["doc-1"],
      contributing_documents: [{ id: "doc-1", original_filename: "doc1.pdf", character_count: 500 }],
      excluded_documents: [],
      total_nodes: 1,
      total_edges: 0,
      depth: "standard",
    },
  };

  stubFetchOnce(200, mockGraph);

  const result = await generateVisualizeGraph({
    documentIds: ["doc-1", "doc-2"],
    depth: "in-depth",
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/study\/visualize\/graph$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    document_ids: ["doc-1", "doc-2"],
    depth: "in-depth",
  });
  assert.equal(result.title, "Operating Systems Concept Network");
  assert.equal(result.nodes.length, 1);
});

test("generateVisualizeGraph translates 502 into friendly message", async () => {
  stubFetchOnce(502, { detail: "Upstream AI failure" });

  await assert.rejects(
    async () => {
      await generateVisualizeGraph({ documentIds: ["doc-1"] });
    },
    {
      name: "Error",
      message: "The AI couldn't generate a concept visualization right now. Please try again in a moment.",
    }
  );
});

test("generateVisualizeGraph propagates guest limit errors with code and limit_type", async () => {
  stubFetchOnce(403, {
    detail: {
      code: "guest_limit_reached",
      limit_type: "ai_generation",
      limit: 5,
      used: 5,
      message: "Guest AI generation limit reached.",
    },
  });

  try {
    await generateVisualizeGraph({ documentIds: ["doc-1"] });
    assert.fail("should have thrown");
  } catch (err) {
    assert.equal(isGuestLimitError(err), true);
    assert.equal(err.code, "guest_limit_reached");
    assert.equal(err.limitType, "ai_generation");
  }
});

test("generateVisualizeGraph translates standard 400 error", async () => {
  stubFetchOnce(400, { detail: "No readable documents available for study." });

  await assert.rejects(
    async () => {
      await generateVisualizeGraph({ documentIds: ["doc-1"] });
    },
    {
      name: "Error",
      message: "No readable documents available for study.",
    }
  );
});
