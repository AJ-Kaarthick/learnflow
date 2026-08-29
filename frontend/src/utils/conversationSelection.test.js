import assert from "node:assert/strict";
import { test } from "node:test";
import {
  removeConversationFromList,
  resolveActiveConversationId,
  renameConversationInList,
  touchConversation,
  withNewConversation,
} from "./conversationSelection.js";

function summary(overrides) {
  return {
    id: "conv-1",
    title: "New Conversation",
    title_is_custom: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

// --- resolveActiveConversationId: "conversation list loading" +
// "selecting an active conversation" -----------------------------------

test("resolveActiveConversationId restores the persisted id when it's still in the list", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" })];
  assert.equal(resolveActiveConversationId(conversations, "b"), "b");
});

test("resolveActiveConversationId falls back to the most recent conversation when the persisted id no longer resolves", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" })];
  assert.equal(resolveActiveConversationId(conversations, "deleted-elsewhere"), "a");
});

test("resolveActiveConversationId falls back to the most recent conversation when nothing was persisted", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" })];
  assert.equal(resolveActiveConversationId(conversations, null), "a");
});

test("resolveActiveConversationId returns null when there are no conversations yet", () => {
  assert.equal(resolveActiveConversationId([], "anything"), null);
  assert.equal(resolveActiveConversationId([], null), null);
});

// --- withNewConversation: "creating a new conversation" + "previous
// conversation remaining intact after creating a new one" ---------------

test("withNewConversation puts the new conversation at the front of the list", () => {
  const existing = [summary({ id: "old-1" }), summary({ id: "old-2" })];
  const created = summary({ id: "new-1", title: "New Conversation" });

  const result = withNewConversation(existing, created);

  assert.equal(result[0].id, "new-1");
  assert.equal(result.length, 3);
});

test("withNewConversation leaves every previous conversation intact — same fields, same order relative to each other", () => {
  const oldA = summary({ id: "old-a", title: "Photosynthesis notes" });
  const oldB = summary({ id: "old-b", title: "Chapter 4 review" });
  const created = summary({ id: "new-1" });

  const result = withNewConversation([oldA, oldB], created);

  // Neither previous conversation was removed, mutated, or reordered
  // relative to each other -- only the new one was inserted ahead of
  // both.
  assert.deepEqual(
    result.filter((conversation) => conversation.id !== "new-1"),
    [oldA, oldB]
  );
});

test("withNewConversation does not mutate the array it was given", () => {
  const existing = [summary({ id: "old-1" })];
  const existingCopy = [...existing];

  withNewConversation(existing, summary({ id: "new-1" }));

  assert.deepEqual(existing, existingCopy);
});

test("withNewConversation de-duplicates defensively if called twice for the same conversation", () => {
  const created = summary({ id: "new-1" });
  const once = withNewConversation([], created);
  const twice = withNewConversation(once, created);

  assert.equal(twice.length, 1);
});

// --- touchConversation: local re-ordering after a message send ---------

test("touchConversation moves the conversation that was just messaged to the front", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" }), summary({ id: "c" })];

  const result = touchConversation(conversations, "c", "2026-02-01T00:00:00Z");

  assert.deepEqual(result.map((conversation) => conversation.id), ["c", "a", "b"]);
});

test("touchConversation updates only the touched conversation's updated_at", () => {
  const conversations = [
    summary({ id: "a", updated_at: "2026-01-01T00:00:00Z" }),
    summary({ id: "b", updated_at: "2026-01-01T00:00:00Z" }),
  ];

  const result = touchConversation(conversations, "b", "2026-03-01T00:00:00Z");

  const touched = result.find((conversation) => conversation.id === "b");
  const untouched = result.find((conversation) => conversation.id === "a");
  assert.equal(touched.updated_at, "2026-03-01T00:00:00Z");
  assert.equal(untouched.updated_at, "2026-01-01T00:00:00Z");
});

test("touchConversation is a no-op when the conversation id isn't in the list", () => {
  const conversations = [summary({ id: "a" })];
  const result = touchConversation(conversations, "not-in-list", "2026-03-01T00:00:00Z");
  assert.deepEqual(result, conversations);
});

// --- renameConversationInList: manual conversation renaming ---------

test("renameConversationInList updates only the renamed conversation's title", () => {
  const conversations = [summary({ id: "a", title: "New Conversation" }), summary({ id: "b", title: "Old title" })];

  const result = renameConversationInList(conversations, "b", "Photosynthesis notes");

  assert.equal(result.find((c) => c.id === "a").title, "New Conversation");
  assert.equal(result.find((c) => c.id === "b").title, "Photosynthesis notes");
});

test("renameConversationInList does not reorder the list (a rename is not an activity event)", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" }), summary({ id: "c" })];

  const result = renameConversationInList(conversations, "c", "Renamed");

  assert.deepEqual(result.map((c) => c.id), ["a", "b", "c"]);
});

test("renameConversationInList leaves updated_at and every other field untouched", () => {
  const conversations = [summary({ id: "a", updated_at: "2026-01-01T00:00:00Z", title_is_custom: false })];

  const result = renameConversationInList(conversations, "a", "New title");

  assert.equal(result[0].updated_at, "2026-01-01T00:00:00Z");
  assert.equal(result[0].title, "New title");
});

test("renameConversationInList is a no-op when the conversation id isn't in the list", () => {
  const conversations = [summary({ id: "a" })];
  const result = renameConversationInList(conversations, "not-in-list", "New title");
  assert.deepEqual(result, conversations);
});

// --- removeConversationFromList: conversation deletion (V2.4 Milestone
// 2 Phase 3 QA fix, issue 1) --------------------------------------------

test("removeConversationFromList removes exactly the deleted conversation", () => {
  const conversations = [summary({ id: "a" }), summary({ id: "b" }), summary({ id: "c" })];

  const result = removeConversationFromList(conversations, "b");

  assert.deepEqual(result.map((conversation) => conversation.id), ["a", "c"]);
});

test("removeConversationFromList leaves every remaining conversation's fields and relative order untouched", () => {
  const a = summary({ id: "a", title: "Photosynthesis notes" });
  const b = summary({ id: "b", title: "Chapter 4 review" });
  const c = summary({ id: "c", title: "To be deleted" });

  const result = removeConversationFromList([a, b, c], "c");

  assert.deepEqual(result, [a, b]);
});

test("removeConversationFromList can empty the list entirely (deleting the last conversation)", () => {
  const result = removeConversationFromList([summary({ id: "only-one" })], "only-one");
  assert.deepEqual(result, []);
});

test("removeConversationFromList is a no-op when the conversation id isn't in the list", () => {
  const conversations = [summary({ id: "a" })];
  const result = removeConversationFromList(conversations, "not-in-list");
  assert.deepEqual(result, conversations);
});

test("removeConversationFromList does not mutate the array it was given", () => {
  const existing = [summary({ id: "a" }), summary({ id: "b" })];
  const existingCopy = [...existing];

  removeConversationFromList(existing, "a");

  assert.deepEqual(existing, existingCopy);
});
