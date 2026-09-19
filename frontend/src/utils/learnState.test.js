import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyOutlineResponse,
  applyTopicResponse,
  createInitialLearnSession,
  findSubtopicById,
  findTopicById,
  formatContributingDocuments,
  getTopicCacheKey,
  getTopicContent,
  isSelectionOutdated,
  LEARN_ACTIONS,
  LEARN_DEPTHS,
} from "./learnState.js";

test("LEARN_DEPTHS defines overview, standard, and in-depth", () => {
  const ids = LEARN_DEPTHS.map((d) => d.id);
  assert.deepEqual(ids, ["overview", "standard", "in-depth"]);
});

test("LEARN_ACTIONS defines simplify, elaborate, and example", () => {
  const ids = LEARN_ACTIONS.map((a) => a.id);
  assert.deepEqual(ids, ["simplify", "elaborate", "example"]);
});

test("createInitialLearnSession initializes correct default state", () => {
  const session = createInitialLearnSession("standard");
  assert.equal(session.outline, null);
  assert.equal(session.selectedTopicId, null);
  assert.deepEqual(session.topicCache, {});
  assert.equal(session.activeDepth, "standard");
  assert.equal(session.activeAction, null);
  assert.equal(session.status, "idle");
  assert.deepEqual(session.documentIds, []);
});

test("getTopicCacheKey produces unique, deterministic composite keys", () => {
  assert.equal(getTopicCacheKey("topic_1", "standard", null), "topic_1::standard::default");
  assert.equal(getTopicCacheKey("topic_1", "standard", "simplify"), "topic_1::standard::simplify");
  assert.equal(getTopicCacheKey("topic_1", "in-depth", "elaborate"), "topic_1::in-depth::elaborate");
  assert.equal(getTopicCacheKey("topic_2", "overview", "example"), "topic_2::overview::example");
});

test("applyOutlineResponse resets cache and records documentIds", () => {
  const initial = createInitialLearnSession();
  const outline = {
    document_ids: ["doc-1", "doc-2"],
    title: "Course Title",
    topics: [{ id: "t1", title: "Topic 1" }],
  };

  const updated = applyOutlineResponse(initial, outline);
  assert.deepEqual(updated.outline, outline);
  assert.deepEqual(updated.documentIds, ["doc-1", "doc-2"]);
  assert.deepEqual(updated.topicCache, {});
  assert.equal(updated.selectedTopicId, null);
  assert.equal(updated.status, "idle");
});

test("applyTopicResponse caches topic response under composite key", () => {
  const session = createInitialLearnSession();
  const topicResp = {
    topic_id: "t1",
    topic_title: "Topic 1",
    depth: "standard",
    action: null,
    explanation: "Standard explanation",
  };

  const next = applyTopicResponse(session, topicResp);
  assert.equal(next.selectedTopicId, "t1");
  assert.equal(next.activeAction, null);
  assert.equal(next.activeDepth, "standard");

  const cached = getTopicContent(next, "t1", "standard", null);
  assert.deepEqual(cached, topicResp);
});

test("getTopicContent returns null for uncached action or depth", () => {
  const session = createInitialLearnSession();
  const topicResp = {
    topic_id: "t1",
    topic_title: "Topic 1",
    depth: "standard",
    action: null,
    explanation: "Standard explanation",
  };

  const next = applyTopicResponse(session, topicResp);
  assert.equal(getTopicContent(next, "t1", "standard", "simplify"), null);
  assert.equal(getTopicContent(next, "t1", "in-depth", null), null);
});

test("switching actions caches each variation separately without destroying base topic", () => {
  let session = createInitialLearnSession();
  const baseResp = {
    topic_id: "t1",
    topic_title: "Topic 1",
    depth: "standard",
    action: null,
    explanation: "Base explanation",
  };
  const simplifyResp = {
    topic_id: "t1",
    topic_title: "Topic 1",
    depth: "standard",
    action: "simplify",
    explanation: "Simplified explanation",
  };

  session = applyTopicResponse(session, baseResp);
  session = applyTopicResponse(session, simplifyResp);

  // Both exist simultaneously in cache
  assert.equal(getTopicContent(session, "t1", "standard", null)?.explanation, "Base explanation");
  assert.equal(getTopicContent(session, "t1", "standard", "simplify")?.explanation, "Simplified explanation");
});

test("isSelectionOutdated detects changed document IDs", () => {
  const session = {
    outline: { title: "Test" },
    documentIds: ["doc-1", "doc-2"],
  };

  // Same IDs
  assert.equal(isSelectionOutdated(session, ["doc-1", "doc-2"]), false);
  assert.equal(isSelectionOutdated(session, ["doc-2", "doc-1"]), false);

  // Different IDs (added, removed, replaced)
  assert.equal(isSelectionOutdated(session, ["doc-1"]), true);
  assert.equal(isSelectionOutdated(session, ["doc-1", "doc-2", "doc-3"]), true);
  assert.equal(isSelectionOutdated(session, ["doc-3", "doc-4"]), true);
});

test("isSelectionOutdated returns false when outline is not yet generated", () => {
  const session = createInitialLearnSession();
  assert.equal(isSelectionOutdated(session, ["doc-1", "doc-2"]), false);
});

test("formatContributingDocuments formats filenames correctly", () => {
  assert.equal(formatContributingDocuments([]), "");
  assert.equal(formatContributingDocuments([{ original_filename: "doc1.pdf" }]), "doc1.pdf");
  assert.equal(
    formatContributingDocuments([
      { original_filename: "doc1.pdf" },
      { original_filename: "doc2.pdf" },
    ]),
    "doc1.pdf and doc2.pdf"
  );
  assert.equal(
    formatContributingDocuments([
      { original_filename: "doc1.pdf" },
      { original_filename: "doc2.pdf" },
      { original_filename: "doc3.pdf" },
    ]),
    "doc1.pdf, doc2.pdf, and doc3.pdf"
  );
});

test("findTopicById and findSubtopicById locate items correctly", () => {
  const outline = {
    topics: [
      {
        id: "t1",
        title: "Topic 1",
        subtopics: [{ id: "s1", title: "Subtopic 1" }],
      },
      { id: "t2", title: "Topic 2" },
    ],
  };

  const t1 = findTopicById(outline, "t1");
  assert.equal(t1?.title, "Topic 1");
  assert.equal(findTopicById(outline, "nonexistent"), null);

  const s1 = findSubtopicById(t1, "s1");
  assert.equal(s1?.title, "Subtopic 1");
  assert.equal(findSubtopicById(t1, "nonexistent"), null);
});
