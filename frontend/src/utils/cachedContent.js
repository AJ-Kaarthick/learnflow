/**
 * Merges a freshly generated study-tool result (summary, flashcards,
 * quiz, or mind map) into the existing cachedContent object.
 *
 * Extracted out of StudyPage.jsx (the old combined HomePage, before V2.4
 * Milestone 1 split it into pages) as its own pure function purely so
 * the actual fix for the "generated content disappears when
 * switching study tabs" bug has a real, isolated unit test (see
 * cachedContent.test.js) — StudyPage.jsx itself has no test harness
 * set up, but this one function is the entire fix, and it doesn't
 * need React or a DOM to verify.
 *
 * `previous` can be null (a document with nothing generated yet, or
 * before cachedContent has loaded at all) — treated the same as an
 * empty object rather than throwing, since StudyPage's cachedContent
 * state itself starts as null.
 */
export function mergeGeneratedContent(previous, kind, value) {
  return { ...(previous ?? {}), [kind]: value };
}
