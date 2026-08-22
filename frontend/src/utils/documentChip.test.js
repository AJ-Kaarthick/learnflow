import assert from "node:assert/strict";
import { test } from "node:test";
import { toDocumentChip } from "./documentChip.js";
import { describeUnreadableDocuments, splitDocumentsByReadability } from "./documentReadiness.js";

// Regression coverage for: "The Chat UX polish fix (naming the
// unreadable document by filename, and not blocking the readable
// ones) works in unit tests but not in the actual app." The bug
// wasn't in ChatPanel's readiness logic itself (documentReadiness.js
// — already covered by documentReadiness.test.js) — it was that
// ChatPage's selectedDocuments chips never carried `status`/
// `character_count` down to ChatPanel in the first place, so
// hasNoReadableText(chip) was always false regardless of the real
// document. These tests exercise the same full pipeline ChatPage ->
// ChatPanel actually uses — toDocumentChip() feeding
// splitDocumentsByReadability()/describeUnreadableDocuments() — not
// just the readiness functions in isolation, so a future regression
// that drops a field again fails a test instead of only showing up in
// manual testing.

// A full DocumentResponse as the backend actually returns it (see
// DocumentResponse.from_document) — every chip-building call site in
// ChatPage.jsx (library selection, upload, rename, restoring a
// persisted selection) has exactly this shape in hand.
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

test("toDocumentChip keeps id and original_filename (what the chip UI displays)", () => {
  const chip = toDocumentChip(fullDocument({ id: "abc", original_filename: "Notes.pdf" }));
  assert.equal(chip.id, "abc");
  assert.equal(chip.original_filename, "Notes.pdf");
});

test("toDocumentChip keeps status and character_count (what readiness checks need)", () => {
  const readable = toDocumentChip(fullDocument({ status: "ready", character_count: 500 }));
  assert.equal(readable.status, "ready");
  assert.equal(readable.character_count, 500);

  const unreadable = toDocumentChip(fullDocument({ status: "ready", character_count: 0 }));
  assert.equal(unreadable.status, "ready");
  assert.equal(unreadable.character_count, 0);
});

test("a chip built by toDocumentChip is correctly classified as unreadable", () => {
  const chip = toDocumentChip(fullDocument({ status: "ready", character_count: 0 }));
  const { readable, unreadable } = splitDocumentsByReadability([chip]);
  assert.deepEqual(readable, []);
  assert.deepEqual(unreadable, [chip]);
});

test("a chip built by toDocumentChip is correctly classified as readable", () => {
  const chip = toDocumentChip(fullDocument({ status: "ready", character_count: 500 }));
  const { readable, unreadable } = splitDocumentsByReadability([chip]);
  assert.deepEqual(readable, [chip]);
  assert.deepEqual(unreadable, []);
});

// The exact manually-reported scenario: "Timetable final 2.pdf"
// (readable) + "Yin and Yang Wallpaper.jpg" (no readable text)
// selected together in Chat.
test("full pipeline: 1 readable + 1 unreadable names the exact offending filename, keeps the readable one usable", () => {
  const timetable = fullDocument({
    id: "t1",
    original_filename: "Timetable final 2.pdf",
    status: "ready",
    character_count: 4200,
  });
  const yinYang = fullDocument({
    id: "y1",
    original_filename: "Yin and Yang Wallpaper.jpg",
    status: "ready",
    character_count: 0,
  });

  const selectedDocuments = [timetable, yinYang].map(toDocumentChip);
  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);

  assert.deepEqual(readable.map((document) => document.id), ["t1"]);
  assert.deepEqual(unreadable.map((document) => document.id), ["y1"]);

  const message = describeUnreadableDocuments(unreadable, readable.length);
  assert.match(message, /Yin and Yang Wallpaper\.jpg/);
  assert.doesNotMatch(message, /Timetable final 2\.pdf/);
  assert.match(message, /still available to chat with/);
  // The old bug: every selected document (including the readable one)
  // ended up in the same "couldn't prepare documents" bucket.
  assert.doesNotMatch(message, /couldn't prepare/i);
});

test("full pipeline: multiple readable + one unreadable isolates only the unreadable one", () => {
  const a = fullDocument({ id: "a", original_filename: "A.pdf", character_count: 100 });
  const b = fullDocument({ id: "b", original_filename: "B.pdf", character_count: 200 });
  const scan = fullDocument({ id: "s", original_filename: "Scan.jpg", character_count: 0 });

  const selectedDocuments = [a, b, scan].map(toDocumentChip);
  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);

  assert.deepEqual(readable.map((document) => document.id), ["a", "b"]);
  assert.deepEqual(unreadable.map((document) => document.id), ["s"]);

  const message = describeUnreadableDocuments(unreadable, readable.length);
  assert.match(message, /Scan\.jpg/);
  assert.match(message, /other documents you selected are still available/);
});

test("full pipeline: all selected documents unreadable names every offending file, no reassurance", () => {
  const scan1 = fullDocument({ id: "s1", original_filename: "Scan1.jpg", character_count: 0 });
  const scan2 = fullDocument({ id: "s2", original_filename: "Scan2.jpg", character_count: 0 });

  const selectedDocuments = [scan1, scan2].map(toDocumentChip);
  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);

  assert.deepEqual(readable, []);
  assert.deepEqual(unreadable.map((document) => document.id), ["s1", "s2"]);

  const message = describeUnreadableDocuments(unreadable, readable.length);
  assert.match(message, /Scan1\.jpg and Scan2\.jpg/);
  assert.doesNotMatch(message, /still available to chat with/);
});

test("full pipeline: a single readable document produces no unreadable-documents notice", () => {
  const timetable = fullDocument({ id: "t1", original_filename: "Timetable final 2.pdf", character_count: 4200 });

  const selectedDocuments = [timetable].map(toDocumentChip);
  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);

  assert.deepEqual(readable.map((document) => document.id), ["t1"]);
  assert.deepEqual(unreadable, []);
  assert.equal(describeUnreadableDocuments(unreadable, readable.length), null);
});

test("full pipeline: a single unreadable document names it and offers no false reassurance", () => {
  const yinYang = fullDocument({
    id: "y1",
    original_filename: "Yin and Yang Wallpaper.jpg",
    character_count: 0,
  });

  const selectedDocuments = [yinYang].map(toDocumentChip);
  const { readable, unreadable } = splitDocumentsByReadability(selectedDocuments);

  assert.deepEqual(readable, []);
  assert.deepEqual(unreadable.map((document) => document.id), ["y1"]);

  const message = describeUnreadableDocuments(unreadable, readable.length);
  assert.match(message, /Yin and Yang Wallpaper\.jpg/);
  assert.doesNotMatch(message, /still available to chat with/);
});
