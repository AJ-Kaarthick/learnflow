import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { isGuestLimitError } from "./errors.js";
import { generateLearnOutline, generateLearnTopic } from "./learn.js";

let originalFetch;
let calls;

beforeEach(() => {
  originalFetch = globalThis.fetch;
  calls = [];
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function stubFetchOnce(status, body) {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  };
}

test("generateLearnOutline sends POST with correct body and credentials", async () => {
  const mockOutline = {
    document_ids: ["doc-1", "doc-2"],
    title: "Intro to Machine Learning",
    description: "Curriculum overview",
    topics: [
      { id: "topic_1", title: "Linear Models", description: "Regression and classification" },
    ],
    grounding_metadata: {
      document_ids: ["doc-1", "doc-2"],
      contributing_documents: [{ id: "doc-1", original_filename: "doc1.pdf", character_count: 500 }],
      excluded_documents: [],
      total_topics: 1,
      depth: "standard",
    },
  };

  stubFetchOnce(200, mockOutline);

  const result = await generateLearnOutline({
    documentIds: ["doc-1", "doc-2"],
    depth: "standard",
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/study\/learn\/outline$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    document_ids: ["doc-1", "doc-2"],
    depth: "standard",
  });
  assert.deepEqual(result, mockOutline);
});

test("generateLearnOutline passes depth parameter", async () => {
  stubFetchOnce(200, { title: "Overview", topics: [] });

  await generateLearnOutline({
    documentIds: ["doc-1"],
    depth: "overview",
  });

  assert.equal(calls.length, 1);
  const parsed = JSON.parse(calls[0].options.body);
  assert.equal(parsed.depth, "overview");
});

test("generateLearnOutline throws GuestLimitError on 429 guest limit rejection", async () => {
  stubFetchOnce(429, {
    detail: {
      code: "guest_limit_reached",
      limit_type: "ai_generation",
      limit: 5,
      used: 5,
      message: "Guests can generate study materials up to 5 times. Sign up for a free account to keep going.",
    },
  });

  await assert.rejects(
    () => generateLearnOutline({ documentIds: ["doc-1"] }),
    (error) => {
      assert.ok(isGuestLimitError(error));
      assert.equal(error.code, "guest_limit_reached");
      assert.match(error.message, /Guests can generate study materials up to 5 times/);
      return true;
    }
  );
});

test("generateLearnOutline maps 502 to friendly AI error message", async () => {
  stubFetchOnce(502, { detail: "OpenAI rate limit exceeded" });

  await assert.rejects(
    () => generateLearnOutline({ documentIds: ["doc-1"] }),
    (error) => {
      assert.equal(
        error.message,
        "The AI couldn't generate a curriculum right now. Please try again in a moment."
      );
      return true;
    }
  );
});

test("generateLearnOutline propagates 400 validation / readiness errors", async () => {
  stubFetchOnce(400, {
    detail: "No readable documents available for study. Please select at least one ready document with readable text.",
  });

  await assert.rejects(
    () => generateLearnOutline({ documentIds: ["doc-unready"] }),
    (error) => {
      assert.match(error.message, /No readable documents available for study/);
      return true;
    }
  );
});

test("generateLearnTopic sends POST with topic_id and topic_title", async () => {
  const mockTopic = {
    topic_id: "topic_1",
    topic_title: "Linear Regression",
    explanation: "# Linear Regression\n\nExplanation text...",
    key_terms: [{ term: "Slope", definition: "Rate of change" }],
    key_takeaways: ["Minimizes squared errors"],
    sources: [
      {
        document_id: "doc-1",
        document_name: "lecture.pdf",
        chunk_id: "chk-1",
        chunk_index: 0,
        content: "excerpt content",
        score: 0.95,
      },
    ],
    grounding_metadata: {
      grounded: true,
      retrieved_chunks_count: 1,
      document_ids: ["doc-1"],
      depth: "standard",
      action: null,
    },
  };

  stubFetchOnce(200, mockTopic);

  const result = await generateLearnTopic({
    documentIds: ["doc-1"],
    topicId: "topic_1",
    topicTitle: "Linear Regression",
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/study\/learn\/topic$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    document_ids: ["doc-1"],
    topic_id: "topic_1",
    topic_title: "Linear Regression",
    action: null,
    depth: "standard",
  });
  assert.deepEqual(result, mockTopic);
});

test("generateLearnTopic sends contextual action and depth controls", async () => {
  stubFetchOnce(200, { topic_id: "t1", explanation: "Simplified" });

  await generateLearnTopic({
    documentIds: ["doc-1", "doc-2"],
    topicId: "t1",
    topicTitle: "Neural Networks",
    action: "simplify",
    depth: "in-depth",
    parentTopicTitle: "Deep Learning",
    context: "introductory module",
  });

  assert.equal(calls.length, 1);
  const parsed = JSON.parse(calls[0].options.body);
  assert.equal(parsed.action, "simplify");
  assert.equal(parsed.depth, "in-depth");
  assert.equal(parsed.parent_topic_title, "Deep Learning");
  assert.equal(parsed.context, "introductory module");
  assert.deepEqual(parsed.document_ids, ["doc-1", "doc-2"]);
});

test("generateLearnTopic throws GuestLimitError on 429 quota exhaustion", async () => {
  stubFetchOnce(429, {
    detail: {
      code: "guest_limit_reached",
      limit_type: "ai_generation",
      limit: 5,
      used: 5,
      message: "Guests can generate study materials up to 5 times. Sign up for a free account to keep going.",
    },
  });

  await assert.rejects(
    () =>
      generateLearnTopic({
        documentIds: ["doc-1"],
        topicId: "t1",
        topicTitle: "Title",
      }),
    (error) => {
      assert.ok(isGuestLimitError(error));
      return true;
    }
  );
});

test("generateLearnTopic maps 502 to friendly AI error message", async () => {
  stubFetchOnce(502, { detail: "Upstream provider timed out" });

  await assert.rejects(
    () =>
      generateLearnTopic({
        documentIds: ["doc-1"],
        topicId: "t1",
        topicTitle: "Title",
      }),
    (error) => {
      assert.equal(
        error.message,
        "The AI couldn't generate this topic explanation right now. Please try again in a moment."
      );
      return true;
    }
  );
});
