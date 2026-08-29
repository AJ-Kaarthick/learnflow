import assert from "node:assert/strict";
import { test } from "node:test";
import { appendPersistedTurn, toInternalMessage, toInternalMessages } from "./conversationMessages.js";

// A persisted message as MessageResponse.from_message actually returns
// it (see schemas/conversation.py) -- every call site here has exactly
// this shape in hand, whether from GET /conversations/{id}'s `messages`
// array or from a send_message response's user_message/assistant_message.
function persistedMessage(overrides) {
  return {
    id: "msg-1",
    role: "user",
    content: "What is this document about?",
    position: 1,
    created_at: "2026-01-15T09:30:00Z",
    sources: null,
    grounded: null,
    ...overrides,
  };
}

// --- toInternalMessage ---------------------------------------------

test("toInternalMessage keeps id, role, and content as-is", () => {
  const message = toInternalMessage(persistedMessage({ id: "abc", role: "assistant", content: "It's about X." }));
  assert.equal(message.id, "abc");
  assert.equal(message.role, "assistant");
  assert.equal(message.content, "It's about X.");
});

test("toInternalMessage converts created_at into an epoch-ms timestamp", () => {
  const message = toInternalMessage(persistedMessage({ created_at: "2026-01-15T09:30:00Z" }));
  assert.equal(message.createdAt, Date.parse("2026-01-15T09:30:00Z"));
  assert.equal(typeof message.createdAt, "number");
});

test("toInternalMessage falls back to null createdAt for a missing/unparsable timestamp", () => {
  assert.equal(toInternalMessage(persistedMessage({ created_at: null })).createdAt, null);
  assert.equal(toInternalMessage(persistedMessage({ created_at: "not-a-date" })).createdAt, null);
});

test("toInternalMessage passes sources and grounded through untouched", () => {
  const sources = [{ chunk_id: "c1", content: "excerpt", score: 0.9, document_id: "d1", document_name: "A.pdf" }];
  const message = toInternalMessage(persistedMessage({ sources, grounded: true }));
  assert.deepEqual(message.sources, sources);
  assert.equal(message.grounded, true);
});

test("toInternalMessage leaves sources as null for a user message (never grounded)", () => {
  const message = toInternalMessage(persistedMessage({ role: "user", sources: null, grounded: null }));
  assert.equal(message.sources, null);
  assert.equal(message.grounded, null);
});

// --- toInternalMessages: "loading messages/documents for the selected
// conversation" -------------------------------------------------------

test("toInternalMessages maps every message, preserving order", () => {
  const messages = [
    persistedMessage({ id: "1", position: 1, role: "user", content: "Q1" }),
    persistedMessage({ id: "2", position: 2, role: "assistant", content: "A1" }),
  ];
  const result = toInternalMessages(messages);
  assert.deepEqual(result.map((message) => message.id), ["1", "2"]);
  assert.deepEqual(result.map((message) => message.content), ["Q1", "A1"]);
});

test("toInternalMessages returns [] for an empty or missing conversation history", () => {
  assert.deepEqual(toInternalMessages([]), []);
  assert.deepEqual(toInternalMessages(undefined), []);
  assert.deepEqual(toInternalMessages(null), []);
});

// This is the direct unit-level proof behind "protection against state
// from conversation A leaking into conversation B": mapping conversation
// A's messages, then conversation B's, must never let anything from A
// show up in B's result (no shared references, no memoized/stale data),
// regardless of call order.
test("toInternalMessages never leaks messages between two different conversations, called in either order", () => {
  const conversationAMessages = [persistedMessage({ id: "a1", content: "About document A" })];
  const conversationBMessages = [
    persistedMessage({ id: "b1", content: "About document B" }),
    persistedMessage({ id: "b2", content: "Follow-up about B" }),
  ];

  const firstA = toInternalMessages(conversationAMessages);
  const firstB = toInternalMessages(conversationBMessages);
  assert.deepEqual(firstA.map((m) => m.id), ["a1"]);
  assert.deepEqual(firstB.map((m) => m.id), ["b1", "b2"]);

  // Same two conversations, called in the opposite order -- the result
  // for each must be identical either way, and neither array should
  // share object references with the other.
  const secondB = toInternalMessages(conversationBMessages);
  const secondA = toInternalMessages(conversationAMessages);
  assert.deepEqual(secondA, firstA);
  assert.deepEqual(secondB, firstB);
  assert.notEqual(secondA, firstA); // distinct array instances
  assert.ok(secondA.every((message) => !secondB.includes(message)));
});

// --- appendPersistedTurn: reconciling the optimistic user bubble ------

test("appendPersistedTurn replaces the optimistic user message and appends the persisted turn", () => {
  const optimistic = { id: "temp-123", role: "user", content: "What's the deadline?", createdAt: 1000 };
  const messages = [optimistic];

  const response = {
    user_message: persistedMessage({ id: "real-user-1", content: "What's the deadline?" }),
    assistant_message: persistedMessage({
      id: "real-assistant-1",
      role: "assistant",
      content: "The deadline is Friday.",
      sources: [{ chunk_id: "c1", content: "Due Friday.", score: 0.95 }],
      grounded: true,
    }),
  };

  const result = appendPersistedTurn(messages, response, "temp-123");

  assert.equal(result.length, 2);
  assert.equal(result.some((m) => m.id === "temp-123"), false);
  assert.equal(result[0].id, "real-user-1");
  assert.equal(result[1].id, "real-assistant-1");
  assert.equal(result[1].content, "The deadline is Friday.");
});

test("appendPersistedTurn keeps earlier turns in place, only replacing the most recent optimistic message", () => {
  const earlier = [
    { id: "u1", role: "user", content: "First question" },
    { id: "a1", role: "assistant", content: "First answer" },
  ];
  const optimistic = { id: "temp-999", role: "user", content: "Second question" };

  const response = {
    user_message: persistedMessage({ id: "u2", content: "Second question" }),
    assistant_message: persistedMessage({ id: "a2", role: "assistant", content: "Second answer" }),
  };

  const result = appendPersistedTurn([...earlier, optimistic], response, "temp-999");

  assert.deepEqual(result.map((m) => m.id), ["u1", "a1", "u2", "a2"]);
});

test("appendPersistedTurn still appends both persisted messages if the optimistic id isn't found", () => {
  const response = {
    user_message: persistedMessage({ id: "u1" }),
    assistant_message: persistedMessage({ id: "a1", role: "assistant" }),
  };

  const result = appendPersistedTurn([], response, "never-existed");

  assert.deepEqual(result.map((m) => m.id), ["u1", "a1"]);
});
