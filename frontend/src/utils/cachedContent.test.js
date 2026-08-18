import assert from "node:assert/strict";
import { test } from "node:test";
import { mergeGeneratedContent } from "./cachedContent.js";

// Regression coverage for: "Generated Summary/Flashcards/Quiz/Mind Map
// disappears when switching study tabs, even though it's correctly
// persisted in the backend."
//
// Root cause: each *Panel component only ever kept its generated
// content in local state, initialized once from cachedContent when
// mounted. StudyWorkspace conditionally renders only the active
// tab's panel, so switching tabs unmounts it — and switching back
// remounts it from the *original* cachedContent, which was never
// updated after generation. mergeGeneratedContent is the fix: it's
// what each panel's onGenerated callback now calls (via HomePage's
// handleContentGenerated) so cachedContent — the value panels are
// re-initialized from on every remount — actually reflects what was
// just generated. None of this is document-type-specific, so the
// same merge covers PDF, DOCX, PPTX, and OCR (PNG/JPG) documents
// alike; the panels have no idea what format the text came from.

test("merges a summary into an empty cache", () => {
  const result = mergeGeneratedContent(null, "summary", { content: "A summary." });
  assert.deepEqual(result, { summary: { content: "A summary." } });
});

test("merging one tool's result does not clobber another already-cached tool", () => {
  // Reproduces exactly the reported flow: Summary was generated (and
  // cached) first, then the student generates Flashcards on another
  // tab. The Summary must still be there afterward.
  const afterSummary = mergeGeneratedContent(null, "summary", { content: "A summary." });
  const afterFlashcards = mergeGeneratedContent(afterSummary, "flashcards", [
    { id: "1", question: "Q", answer: "A" },
  ]);

  assert.deepEqual(afterFlashcards, {
    summary: { content: "A summary." },
    flashcards: [{ id: "1", question: "Q", answer: "A" }],
  });
});

test("regenerating a tool overwrites only that tool's cached value", () => {
  const first = mergeGeneratedContent(null, "quiz", [{ id: "1", question: "Old" }]);
  const regenerated = mergeGeneratedContent(first, "quiz", [{ id: "2", question: "New" }]);

  assert.deepEqual(regenerated, { quiz: [{ id: "2", question: "New" }] });
});

test("handles all four study tools independently, as StudyWorkspace's tabs do", () => {
  let cache = null;
  cache = mergeGeneratedContent(cache, "summary", { content: "Summary text." });
  cache = mergeGeneratedContent(cache, "flashcards", [{ id: "1" }]);
  cache = mergeGeneratedContent(cache, "quiz", [{ id: "1" }]);
  cache = mergeGeneratedContent(cache, "mindmap", { structure: { title: "Root", children: [] } });

  assert.deepEqual(cache, {
    summary: { content: "Summary text." },
    flashcards: [{ id: "1" }],
    quiz: [{ id: "1" }],
    mindmap: { structure: { title: "Root", children: [] } },
  });
});

test("mindmap merges the same { structure } shape getMindMap/generateMindMap already return", () => {
  // MindMapPanel reads initialMindmap?.structure, so onGenerated must
  // be called with the whole response object (not just .structure) —
  // this pins that contract down.
  const cache = mergeGeneratedContent(null, "mindmap", {
    structure: { title: "Photosynthesis", children: [] },
  });

  assert.equal(cache.mindmap.structure.title, "Photosynthesis");
});

test("works identically regardless of which document format the content came from", () => {
  // The merge itself is document-type-agnostic — this documents that
  // fact explicitly, since the bug report specifically calls out that
  // PDF, DOCX, PPTX, and OCR (PNG/JPG) documents must all be fixed.
  for (const documentKind of ["pdf", "docx", "pptx", "png", "jpg"]) {
    const cache = mergeGeneratedContent(null, "summary", {
      content: `Summary of a ${documentKind} document.`,
    });
    assert.equal(cache.summary.content, `Summary of a ${documentKind} document.`);
  }
});
