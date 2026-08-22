import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveChatUploadSync } from "./documentUploadSync.js";
import { splitDocumentsByReadability } from "./documentReadiness.js";

// Regression coverage for: uploading a document from the Chat page's
// Document Library didn't show up there until a full page refresh (or
// switching to Study and back), even though the upload itself
// succeeded and Study's Document Library updated immediately. Root
// cause: ChatPage.handleUploadComplete only updated its own
// `selectedDocuments` chat-selection state and never bumped the
// `refreshSignal` LibraryPanel actually re-fetches on (see
// LibraryPanel.jsx's `[search, sort, refreshSignal]` effect) — unlike
// StudyPage, whose handleUploadComplete routes through
// handleOpenDocument, which already bumps refreshSignal via
// markDocumentOpened's `.finally()`.
//
// ChatPage.jsx itself can't be rendered in this project's plain
// `node --test` frontend suite (no JSX transform in the test
// pipeline — see documentChip.test.js for the same reasoning), so the
// two things the fix depends on are extracted into
// resolveChatUploadSync (a plain, non-JSX module) and tested here:
// 1. `shouldRefreshLibrary` is always true, regardless of the current
//    selection — this is the actual regression guard: ChatPage wires
//    its refreshSignal bump unconditionally specifically because this
//    contract never varies (see ChatPage.jsx's handleUploadComplete).
// 2. The pre-existing chat-selection merge behavior (single vs.
//    multi-document mode, dedup on re-upload) still behaves exactly
//    as before, so the fix doesn't regress "Preserve existing
//    document selection and multi-document Chat behavior."

// A full DocumentResponse as the backend actually returns it (see
// DocumentResponse.from_document) — matches the shape used in
// documentChip.test.js.
function fullDocument(overrides) {
  return {
    id: "doc-id",
    original_filename: "file.pdf",
    status: "ready",
    created_at: "2026-01-01T00:00:00Z",
    last_opened_at: null,
    text_preview: "preview",
    character_count: 100,
    file_size_bytes: 1024,
    page_count: 1,
    ...overrides,
  };
}

test("shouldRefreshLibrary is true with no prior selection (the exact manual-repro case)", () => {
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { shouldRefreshLibrary } = resolveChatUploadSync([], uploaded);
  assert.equal(shouldRefreshLibrary, true);
});

test("shouldRefreshLibrary is true when replacing a single existing selection", () => {
  const existing = fullDocument({ id: "existing", original_filename: "Old.pdf" });
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { shouldRefreshLibrary } = resolveChatUploadSync([existing], uploaded);
  assert.equal(shouldRefreshLibrary, true);
});

test("shouldRefreshLibrary is true when appending in multi-document mode", () => {
  const a = fullDocument({ id: "a", original_filename: "A.pdf" });
  const b = fullDocument({ id: "b", original_filename: "B.pdf" });
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { shouldRefreshLibrary } = resolveChatUploadSync([a, b], uploaded);
  assert.equal(shouldRefreshLibrary, true);
});

test("shouldRefreshLibrary is true even when the uploaded document is already selected", () => {
  const a = fullDocument({ id: "a", original_filename: "A.pdf" });
  const b = fullDocument({ id: "b", original_filename: "B.pdf" });
  const reuploaded = fullDocument({ id: "a", original_filename: "A.pdf" });
  const { shouldRefreshLibrary } = resolveChatUploadSync([a, b], reuploaded);
  assert.equal(shouldRefreshLibrary, true);
});

test("no prior selection: uploaded document becomes the sole selection", () => {
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { selectedDocuments } = resolveChatUploadSync([], uploaded);
  assert.deepEqual(selectedDocuments.map((doc) => doc.id), ["new-1"]);
});

test("single-document mode: uploading replaces the existing selection", () => {
  const existing = fullDocument({ id: "existing", original_filename: "Old.pdf" });
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { selectedDocuments } = resolveChatUploadSync([existing], uploaded);
  assert.deepEqual(selectedDocuments.map((doc) => doc.id), ["new-1"]);
});

test("multi-document mode: uploading appends without derailing the existing selection", () => {
  const a = fullDocument({ id: "a", original_filename: "A.pdf" });
  const b = fullDocument({ id: "b", original_filename: "B.pdf" });
  const uploaded = fullDocument({ id: "new-1", original_filename: "Notes.pdf" });
  const { selectedDocuments } = resolveChatUploadSync([a, b], uploaded);
  assert.deepEqual(selectedDocuments.map((doc) => doc.id), ["a", "b", "new-1"]);
});

test("multi-document mode: re-uploading an already-selected document does not duplicate its chip", () => {
  const a = fullDocument({ id: "a", original_filename: "A.pdf" });
  const b = fullDocument({ id: "b", original_filename: "B.pdf" });
  const reuploaded = fullDocument({ id: "a", original_filename: "A.pdf", character_count: 999 });
  const { selectedDocuments } = resolveChatUploadSync([a, b], reuploaded);
  assert.deepEqual(selectedDocuments.map((doc) => doc.id), ["a", "b"]);
});

// The chip must carry status/character_count (not just id/filename),
// same requirement documentChip.test.js guards against regressing —
// otherwise a freshly uploaded unreadable document would silently
// look readable to ChatPanel.
test("uploaded document's chip carries readiness fields, and is correctly classified when unreadable", () => {
  const scan = fullDocument({ id: "s1", original_filename: "Scan.jpg", character_count: 0 });
  const { selectedDocuments } = resolveChatUploadSync([], scan);

  assert.equal(selectedDocuments[0].status, "ready");
  assert.equal(selectedDocuments[0].character_count, 0);

  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);
  assert.deepEqual(readable, []);
  assert.deepEqual(unreadable.map((doc) => doc.id), ["s1"]);
});

test("readable + unreadable mix (manual test case 5): uploading a readable doc alongside an already-selected unreadable one keeps both, correctly classified", () => {
  const unreadableExisting = fullDocument({
    id: "y1",
    original_filename: "Yin and Yang Wallpaper.jpg",
    character_count: 0,
  });
  const uploadedReadable = fullDocument({
    id: "t1",
    original_filename: "Timetable final 2.pdf",
    character_count: 4200,
  });

  // Single unreadable document selected, then a readable one is
  // uploaded: single/automatic mode (<=1 selected) replaces, matching
  // handleOpenForChat's click-to-replace behavior for uploads too.
  const { selectedDocuments } = resolveChatUploadSync([unreadableExisting], uploadedReadable);
  assert.deepEqual(selectedDocuments.map((doc) => doc.id), ["t1"]);

  // Now simulate the mixed multi-document case directly: both
  // selected together (e.g. the unreadable doc checked back on after
  // the upload) still splits correctly.
  const { readable, unreadable } = splitDocumentsByReadability([unreadableExisting, uploadedReadable].map(
    (doc) => resolveChatUploadSync([], doc).selectedDocuments[0]
  ));
  assert.deepEqual(readable.map((doc) => doc.id), ["t1"]);
  assert.deepEqual(unreadable.map((doc) => doc.id), ["y1"]);
});
