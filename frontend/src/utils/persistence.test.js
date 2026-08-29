import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { loadActiveConversationId, saveActiveConversationId } from "./persistence.js";

// This project's frontend test suite is plain `node --test`, with no
// DOM/browser environment — persistence.js is written to tolerate
// that (every read/write is try/caught around `window.localStorage`,
// degrading to "nothing was saved" rather than crashing — see this
// module's own docstring). To actually exercise the round trip rather
// than just the no-window fallback path, this test file supplies a
// minimal in-memory localStorage polyfill on `globalThis.window`
// before each test.
class MemoryLocalStorage {
  constructor() {
    this.store = new Map();
  }
  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }
  setItem(key, value) {
    this.store.set(key, String(value));
  }
  removeItem(key) {
    this.store.delete(key);
  }
}

beforeEach(() => {
  globalThis.window = { localStorage: new MemoryLocalStorage() };
});

// "active conversation ID persistence if applicable" -- the one piece
// of conversation state V2.4 Milestone 2 (frontend) still persists to
// localStorage; see persistence.js's DEFAULT_WORKSPACE_STATE comment
// for why nothing else about a conversation is saved here anymore.

test("loadActiveConversationId returns null when nothing has been saved yet", () => {
  assert.equal(loadActiveConversationId(), null);
});

test("saveActiveConversationId then loadActiveConversationId round-trips the id", () => {
  saveActiveConversationId("conv-abc");
  assert.equal(loadActiveConversationId(), "conv-abc");
});

test("saveActiveConversationId(null) clears back to null (e.g. after the active conversation was deleted)", () => {
  saveActiveConversationId("conv-abc");
  assert.equal(loadActiveConversationId(), "conv-abc");

  saveActiveConversationId(null);
  assert.equal(loadActiveConversationId(), null);
});

test("saveActiveConversationId(undefined) is treated the same as null, not saved as the literal string 'undefined'", () => {
  saveActiveConversationId(undefined);
  assert.equal(loadActiveConversationId(), null);
});

test("saving the active conversation id does not disturb other workspace state", async () => {
  const { loadActiveDocumentId, saveActiveDocumentId, loadActiveStudyTab } = await import("./persistence.js");

  saveActiveDocumentId("doc-1");
  saveActiveConversationId("conv-1");

  assert.equal(loadActiveDocumentId(), "doc-1");
  assert.equal(loadActiveConversationId(), "conv-1");
  // Untouched fields keep their defaults.
  assert.equal(loadActiveStudyTab(), "summary");
});

test("a workspace blob saved before this milestone (with the old selectedDocumentIds field, no activeConversationId) still loads, defaulting activeConversationId to null", () => {
  // Simulates a pre-Milestone-2 localStorage entry directly, the way
  // a returning user's browser would already have one -- this
  // module's own merge (`{...DEFAULT_WORKSPACE_STATE, ...stored}`)
  // is what's under test here, not the save path.
  const legacyBlob = JSON.stringify({
    activeDocumentId: "doc-9",
    activeStudyTab: "flashcards",
    selectedDocumentIds: ["doc-9", "doc-10"],
    librarySearch: "",
    librarySort: "uploaded_newest",
    libraryScrollTop: 0,
  });
  globalThis.window.localStorage.setItem("learnflow:workspace:v1", legacyBlob);

  assert.equal(loadActiveConversationId(), null);
});
