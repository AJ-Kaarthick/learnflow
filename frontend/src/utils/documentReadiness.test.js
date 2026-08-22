import assert from "node:assert/strict";
import { test } from "node:test";
import {
  describeUnreadableDocuments,
  hasNoReadableText,
  splitDocumentsByReadability,
} from "./documentReadiness.js";

// Regression coverage for: "Study generation tabs (Summary, Flashcards,
// Quiz, Mind Map) can produce/display AI content even when the
// selected document has no usable readable/extracted text."
//
// hasNoReadableText is the frontend-side half of the fix: it lets
// StudyWorkspace decide, purely from data it already has (no network
// call), whether to render the four Study panels at all or show
// NoReadableTextState instead — see StudyWorkspace.jsx. The backend
// guard (each routes_*.py's own _get_ready_document) remains the
// authoritative check; this only prevents the wasted round trip (and
// keeps a document known to have nothing readable from ever showing a
// "Generate" button in the first place).

test("a ready document with zero extracted characters has no readable text", () => {
  const document = { status: "ready", character_count: 0 };
  assert.equal(hasNoReadableText(document), true);
});

test("a ready document with some extracted characters has readable text", () => {
  const document = { status: "ready", character_count: 1200 };
  assert.equal(hasNoReadableText(document), false);
});

test("a ready document with very little (but nonzero) text is not blocked", () => {
  // Distinct from the "no readable text" case — StudyWorkspace still
  // shows its own separate "very little text" advisory for this
  // range, but generation itself stays available, matching the
  // backend's `not extracted_text.strip()` check (only truly blank
  // text is blocking).
  const document = { status: "ready", character_count: 12 };
  assert.equal(hasNoReadableText(document), false);
});

test("a still-processing document is never considered 'no readable text'", () => {
  // character_count is 0 for a document that hasn't finished
  // extraction yet too — this must not be confused with "extraction
  // finished and found nothing".
  const document = { status: "processing", character_count: 0 };
  assert.equal(hasNoReadableText(document), false);
});

test("a failed document is never considered 'no readable text'", () => {
  const document = { status: "failed", character_count: 0 };
  assert.equal(hasNoReadableText(document), false);
});

test("null/undefined document is handled without throwing", () => {
  assert.equal(hasNoReadableText(null), false);
  assert.equal(hasNoReadableText(undefined), false);
});

// Regression coverage for: "V2.4 Milestone 1 Chat UX polish — when
// multiple documents are selected and one or more has no readable
// text, the warning doesn't say which one." splitDocumentsByReadability
// and describeUnreadableDocuments are what let ChatPanel identify the
// unreadable document(s) by filename while keeping the readable ones
// fully usable — see ChatPanel.jsx.

test("splitDocumentsByReadability separates readable and unreadable documents", () => {
  // The exact scenario from the bug report: Linux-Tutorial.pdf is
  // readable, Enso Wallpaper.jpg is not.
  const linuxTutorial = { id: "doc-1", original_filename: "Linux-Tutorial.pdf", status: "ready", character_count: 4200 };
  const ensoWallpaper = { id: "doc-2", original_filename: "Enso Wallpaper.jpg", status: "ready", character_count: 0 };

  const { readable, unreadable } = splitDocumentsByReadability([linuxTutorial, ensoWallpaper]);

  assert.deepEqual(readable, [linuxTutorial]);
  assert.deepEqual(unreadable, [ensoWallpaper]);
});

test("splitDocumentsByReadability preserves selection order within each group", () => {
  const a = { id: "a", original_filename: "A.pdf", status: "ready", character_count: 10 };
  const b = { id: "b", original_filename: "B.jpg", status: "ready", character_count: 0 };
  const c = { id: "c", original_filename: "C.pdf", status: "ready", character_count: 20 };
  const d = { id: "d", original_filename: "D.jpg", status: "ready", character_count: 0 };

  const { readable, unreadable } = splitDocumentsByReadability([a, b, c, d]);

  assert.deepEqual(readable, [a, c]);
  assert.deepEqual(unreadable, [b, d]);
});

test("splitDocumentsByReadability treats every document as readable when none are blocked", () => {
  const a = { id: "a", original_filename: "A.pdf", status: "ready", character_count: 10 };
  const b = { id: "b", original_filename: "B.pdf", status: "ready", character_count: 20 };

  const { readable, unreadable } = splitDocumentsByReadability([a, b]);

  assert.deepEqual(readable, [a, b]);
  assert.deepEqual(unreadable, []);
});

test("splitDocumentsByReadability treats every document as unreadable when all are blocked", () => {
  const a = { id: "a", original_filename: "A.jpg", status: "ready", character_count: 0 };
  const b = { id: "b", original_filename: "B.jpg", status: "ready", character_count: 0 };

  const { readable, unreadable } = splitDocumentsByReadability([a, b]);

  assert.deepEqual(readable, []);
  assert.deepEqual(unreadable, [a, b]);
});

test("splitDocumentsByReadability handles an empty or missing selection", () => {
  assert.deepEqual(splitDocumentsByReadability([]), { readable: [], unreadable: [] });
  assert.deepEqual(splitDocumentsByReadability(undefined), { readable: [], unreadable: [] });
});

test("describeUnreadableDocuments returns null when nothing is unreadable", () => {
  assert.equal(describeUnreadableDocuments([], 2), null);
});

test("describeUnreadableDocuments names a single unreadable document by filename, singular wording", () => {
  const ensoWallpaper = { original_filename: "Enso Wallpaper.jpg" };

  const message = describeUnreadableDocuments([ensoWallpaper], 1);

  // Requirement 4 (name the actual filename) and requirement 10
  // (which document, why, and that the rest is still usable).
  assert.match(message, /Enso Wallpaper\.jpg/);
  assert.match(message, /has no readable text/);
  assert.doesNotMatch(message, /have no readable text/);
  assert.match(message, /still available to chat with/);
  // Never falls back to a generic, non-identifying phrase.
  assert.doesNotMatch(message, /this document/i);
});

test("describeUnreadableDocuments names multiple unreadable documents, plural wording, Oxford comma", () => {
  const scan = { original_filename: "Scan.png" };
  const wallpaper = { original_filename: "Enso Wallpaper.jpg" };
  const photo = { original_filename: "Vacation Photo.heic" };

  const message = describeUnreadableDocuments([scan, wallpaper, photo], 2);

  assert.match(message, /Scan\.png, Enso Wallpaper\.jpg, and Vacation Photo\.heic/);
  assert.match(message, /have no readable text/);
  assert.match(message, /other documents you selected are still available/);
});

test("describeUnreadableDocuments joins exactly two filenames with 'and', no comma", () => {
  const a = { original_filename: "A.jpg" };
  const b = { original_filename: "B.jpg" };

  const message = describeUnreadableDocuments([a, b], 1);

  assert.match(message, /^A\.jpg and B\.jpg have no readable text/);
});

test("describeUnreadableDocuments drops the reassurance when no readable document remains", () => {
  // The "all selected documents are unreadable" case — single
  // document selected, mirroring the pre-fix single-document flow,
  // just now naming the file instead of saying "this document".
  const ensoWallpaper = { original_filename: "Enso Wallpaper.jpg" };

  const message = describeUnreadableDocuments([ensoWallpaper], 0);

  assert.match(message, /Enso Wallpaper\.jpg/);
  assert.doesNotMatch(message, /still available to chat with/);
  assert.match(message, /Select a document with readable text/);
});

test("describeUnreadableDocuments drops the reassurance for multiple unreadable documents with none readable", () => {
  const a = { original_filename: "A.jpg" };
  const b = { original_filename: "B.jpg" };

  const message = describeUnreadableDocuments([a, b], 0);

  assert.match(message, /A\.jpg and B\.jpg have no readable text/);
  assert.doesNotMatch(message, /still available to chat with/);
});
