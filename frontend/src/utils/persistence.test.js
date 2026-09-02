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

// --- V2.4 Milestone 2 Phase 6 (localStorage migration): regression
// guards proving conversation *content* never re-enters localStorage,
// on top of the round-trip coverage above for the one thing that
// legitimately still does (the active id). Phase 6's own inspection
// found no remaining conversation-message or conversation-document
// persistence anywhere in the frontend (that work was already done
// when this module was rebuilt around the backend-persisted
// Conversation model) -- these tests exist so a future change can't
// quietly reintroduce it without a test failing here first.

test("persistence.js exposes no functions for persisting conversation messages or per-conversation document selections (Phase 6 regression guard)", async () => {
  const persistenceModule = await import("./persistence.js");
  // Names a reintroduced full-conversation cache would plausibly use --
  // including the exact ones this module's own docstring says were
  // removed (loadConversation/saveConversation/clearConversation/
  // getConversationKey) plus the obvious variants.
  const disallowedExportNames = [
    "loadConversation",
    "saveConversation",
    "clearConversation",
    "getConversationKey",
    "loadConversationMessages",
    "saveConversationMessages",
    "loadSelectedDocumentIds",
    "saveSelectedDocumentIds",
    "loadConversationDocuments",
    "saveConversationDocuments",
  ];
  for (const name of disallowedExportNames) {
    assert.equal(
      name in persistenceModule,
      false,
      `persistence.js must not export ${name} -- conversation content is backend-persisted, never cached in localStorage`
    );
  }
});

test("exercising every persistence.js save function only ever writes the workspace/settings keys, never a dedicated conversation-content key (Phase 6 regression guard)", async () => {
  const storage = globalThis.window.localStorage;
  const writtenKeys = new Set();
  const originalSetItem = storage.setItem.bind(storage);
  storage.setItem = (key, value) => {
    writtenKeys.add(key);
    return originalSetItem(key, value);
  };

  const { saveActiveDocumentId, saveActiveStudyTab, saveLibraryFilters, saveLibraryScrollTop, saveSettings } =
    await import("./persistence.js");

  saveActiveConversationId("conv-1");
  saveActiveDocumentId("doc-1");
  saveActiveStudyTab("flashcards");
  saveLibraryFilters({ search: "x", sort: "uploaded_newest" });
  saveLibraryScrollTop(42);
  saveSettings({ theme: "dark", accent: "blue", density: "compact", animations: "enabled" });

  // Only ever two keys total, no matter how many different pieces of
  // state get saved -- in particular, nothing named after a
  // conversation or message, and nothing per-conversation (e.g. a
  // key with a conversation id embedded in it).
  assert.deepEqual([...writtenKeys].sort(), ["learnflow:settings:v1", "learnflow:workspace:v1"]);
});

test("the persisted workspace blob never contains a messages, documents, or selectedDocumentIds array, even after saving the active conversation id (Phase 6 regression guard)", () => {
  saveActiveConversationId("conv-1");
  const raw = globalThis.window.localStorage.getItem("learnflow:workspace:v1");
  const parsed = JSON.parse(raw);

  assert.equal("messages" in parsed, false);
  assert.equal("documents" in parsed, false);
  assert.equal("selectedDocumentIds" in parsed, false);
  // The one conversation-related field that IS expected: an opaque
  // id, not an object/array that could smuggle content alongside it.
  assert.equal(typeof parsed.activeConversationId, "string");
});
