import assert from "node:assert/strict";
import { test } from "node:test";
import {
  MAX_STUDY_DOCUMENTS,
  openStudyDocument,
  removeStudyDocument,
  resolveActiveStudyDocument,
  syncStudyUpload,
  toggleStudyDocument,
} from "./studySelection.js";

const doc1 = { id: 1, original_filename: "Doc1.pdf", status: "ready", character_count: 500 };
const doc2 = { id: 2, original_filename: "Doc2.pdf", status: "ready", character_count: 1000 };
const doc3 = { id: 3, original_filename: "Doc3.pdf", status: "ready", character_count: 750 };
const docUnreadable = { id: 4, original_filename: "Scan.jpg", status: "ready", character_count: 0 };
const docProcessing = { id: 5, original_filename: "Notes.docx", status: "processing", character_count: 0 };

test("MAX_STUDY_DOCUMENTS is exactly 10", () => {
  assert.equal(MAX_STUDY_DOCUMENTS, 10);
});

test("toggleStudyDocument adds a document when not selected", () => {
  const { nextDocuments, error } = toggleStudyDocument([doc1], doc2);
  assert.equal(error, null);
  assert.equal(nextDocuments.length, 2);
  assert.deepEqual(nextDocuments.map((d) => d.id), [1, 2]);
});

test("toggleStudyDocument removes a document when already selected", () => {
  const { nextDocuments, error } = toggleStudyDocument([doc1, doc2], doc1);
  assert.equal(error, null);
  assert.equal(nextDocuments.length, 1);
  assert.equal(nextDocuments[0].id, 2);
});

test("toggleStudyDocument enforces MAX_STUDY_DOCUMENTS limit", () => {
  const current = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    original_filename: `Doc${i + 1}.pdf`,
    status: "ready",
    character_count: 100,
  }));

  const extraDoc = { id: 99, original_filename: "Extra.pdf", status: "ready", character_count: 200 };
  const { nextDocuments, error } = toggleStudyDocument(current, extraDoc);

  assert.equal(nextDocuments.length, 10);
  assert.equal(error, "You can select up to 10 documents for study.");
  assert.equal(nextDocuments.some((d) => d.id === 99), false);
});

test("openStudyDocument replaces selection in single-document mode (0 or 1 doc selected)", () => {
  // 0 selected
  const res0 = openStudyDocument([], doc1);
  assert.equal(res0.error, null);
  assert.equal(res0.nextDocuments.length, 1);
  assert.equal(res0.nextDocuments[0].id, 1);
  assert.equal(res0.activeDocument.id, 1);

  // 1 selected -> replaces with doc2 (classic V2.4 single-document behavior)
  const res1 = openStudyDocument([doc1], doc2);
  assert.equal(res1.error, null);
  assert.equal(res1.nextDocuments.length, 1);
  assert.equal(res1.nextDocuments[0].id, 2);
  assert.equal(res1.activeDocument.id, 2);
});

test("openStudyDocument focuses without modifying selection when already in multi-doc selection", () => {
  const res = openStudyDocument([doc1, doc2, doc3], doc2);
  assert.equal(res.error, null);
  assert.equal(res.nextDocuments.length, 3);
  assert.deepEqual(res.nextDocuments.map((d) => d.id), [1, 2, 3]);
  assert.equal(res.activeDocument.id, 2);
});

test("openStudyDocument appends when not yet in multi-doc selection and under limit", () => {
  const res = openStudyDocument([doc1, doc2], doc3);
  assert.equal(res.error, null);
  assert.equal(res.nextDocuments.length, 3);
  assert.deepEqual(res.nextDocuments.map((d) => d.id), [1, 2, 3]);
  assert.equal(res.activeDocument.id, 3);
});

test("openStudyDocument enforces limit in multi-document mode", () => {
  const current = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    original_filename: `Doc${i + 1}.pdf`,
    status: "ready",
    character_count: 100,
  }));

  const extraDoc = { id: 99, original_filename: "Extra.pdf", status: "ready", character_count: 200 };
  const res = openStudyDocument(current, extraDoc);

  assert.equal(res.nextDocuments.length, 10);
  assert.match(res.error, /You can select up to 10 documents/);
});

test("removeStudyDocument drops the document by id", () => {
  const { nextDocuments } = removeStudyDocument([doc1, doc2, doc3], 2);
  assert.equal(nextDocuments.length, 2);
  assert.deepEqual(nextDocuments.map((d) => d.id), [1, 3]);
});

test("resolveActiveStudyDocument respects preferredActiveId when present", () => {
  const active = resolveActiveStudyDocument([doc1, doc2, doc3], 3);
  assert.equal(active.id, 3);
});

test("resolveActiveStudyDocument prefers first readable document when preferred not found", () => {
  const active = resolveActiveStudyDocument([docUnreadable, doc2, doc3], 999);
  assert.equal(active.id, 2);
});

test("resolveActiveStudyDocument falls back to first document if none are readable", () => {
  const active = resolveActiveStudyDocument([docUnreadable, docProcessing], null);
  assert.equal(active.id, 4);
});

test("resolveActiveStudyDocument returns null for empty list", () => {
  assert.equal(resolveActiveStudyDocument([]), null);
  assert.equal(resolveActiveStudyDocument(null), null);
});

test("syncStudyUpload replaces sole document in single-doc mode", () => {
  const res = syncStudyUpload([doc1], doc2);
  assert.equal(res.nextDocuments.length, 1);
  assert.equal(res.nextDocuments[0].id, 2);
  assert.equal(res.activeDocument.id, 2);
});

test("syncStudyUpload appends to multi-document selection under limit", () => {
  const res = syncStudyUpload([doc1, doc2], doc3);
  assert.equal(res.nextDocuments.length, 3);
  assert.deepEqual(res.nextDocuments.map((d) => d.id), [1, 2, 3]);
  assert.equal(res.activeDocument.id, 3);
});

test("syncStudyUpload deduplicates if uploaded document is already selected", () => {
  const res = syncStudyUpload([doc1, doc2], doc1);
  assert.equal(res.nextDocuments.length, 2);
  assert.equal(res.activeDocument.id, 1);
});
