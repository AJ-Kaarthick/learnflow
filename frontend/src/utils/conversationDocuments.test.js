import assert from "node:assert/strict";
import { test } from "node:test";
import { orderHydratedDocuments } from "./conversationDocuments.js";

// The trimmed shape GET /conversations/{id} embeds in `documents` --
// see ConversationDocumentSummary in schemas/conversation.py. Notably
// missing character_count, which is exactly the gap this module fills.
function conversationDocumentSummary(overrides) {
  return { id: "doc-1", original_filename: "file.pdf", status: "ready", ...overrides };
}

// A full DocumentResponse, as returned by GET /documents/{id} (see
// utils/documentHydration.js's hydrateDocumentIds, which is what
// actually produces these).
function fullDocument(overrides) {
  return {
    id: "doc-1",
    original_filename: "file.pdf",
    status: "ready",
    character_count: 500,
    ...overrides,
  };
}

test("orderHydratedDocuments returns the hydrated records in the conversation's own document order", () => {
  const summaries = [
    conversationDocumentSummary({ id: "b" }),
    conversationDocumentSummary({ id: "a" }),
    conversationDocumentSummary({ id: "c" }),
  ];
  // Deliberately hydrated/returned out of that order -- hydrateDocumentIds
  // explicitly does not guarantee order (parallel fetches).
  const hydrated = [
    fullDocument({ id: "a" }),
    fullDocument({ id: "c" }),
    fullDocument({ id: "b" }),
  ];

  const result = orderHydratedDocuments(summaries, hydrated);

  assert.deepEqual(result.map((document) => document.id), ["b", "a", "c"]);
});

test("orderHydratedDocuments carries character_count through from the hydrated record, not the summary", () => {
  const summaries = [conversationDocumentSummary({ id: "a" })];
  const hydrated = [fullDocument({ id: "a", character_count: 0 })];

  const result = orderHydratedDocuments(summaries, hydrated);

  assert.equal(result[0].character_count, 0);
});

test("orderHydratedDocuments drops a document that failed to hydrate (deleted between the two calls)", () => {
  const summaries = [
    conversationDocumentSummary({ id: "a" }),
    conversationDocumentSummary({ id: "deleted-elsewhere" }),
    conversationDocumentSummary({ id: "c" }),
  ];
  const hydrated = [fullDocument({ id: "a" }), fullDocument({ id: "c" })];

  const result = orderHydratedDocuments(summaries, hydrated);

  assert.deepEqual(result.map((document) => document.id), ["a", "c"]);
});

test("orderHydratedDocuments returns [] for a conversation with no associated documents", () => {
  assert.deepEqual(orderHydratedDocuments([], []), []);
  assert.deepEqual(orderHydratedDocuments(undefined, []), []);
});
