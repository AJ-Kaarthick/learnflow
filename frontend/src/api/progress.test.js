import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import {
  getProgressRecommendations,
  getProgressSummary,
  getProgressTopics,
  getProgressWeakTopics,
  getSpacedRepetitionSchedules,
} from "./progress.js";

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

test("getProgressSummary fetches /api/v1/progress/summary with credentials included", async () => {
  const mockSummary = {
    total_completed_sessions: 3,
    overall_attempt_accuracy: 0.85,
    overall_mastery: { score: 0.75, tier: "proficient", is_assessed: true },
  };
  stubFetchOnce(200, mockSummary);

  const result = await getProgressSummary();

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/progress\/summary$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockSummary);
});

test("getProgressTopics fetches /api/v1/progress/topics with credentials included", async () => {
  const mockTopics = [
    {
      topic_key: "mitosis",
      topic_display: "Mitosis",
      mastery_score: 0.82,
      mastery_tier: "mastered",
    },
  ];
  stubFetchOnce(200, mockTopics);

  const result = await getProgressTopics();

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/progress\/topics$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockTopics);
});

test("getProgressWeakTopics fetches /api/v1/progress/weak-topics with credentials included", async () => {
  const mockWeakTopics = [
    {
      topic_key: "meiosis",
      topic_display: "Meiosis",
      struggle_index: 0.74,
      mastery_score: 0.35,
    },
  ];
  stubFetchOnce(200, mockWeakTopics);

  const result = await getProgressWeakTopics();

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/progress\/weak-topics$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockWeakTopics);
});

test("getSpacedRepetitionSchedules supports boolean and options object for include_unreviewed_active", async () => {
  const mockSchedules = [
    {
      document_id: "doc-1",
      current_streak: 2,
      is_due: true,
    },
  ];
  stubFetchOnce(200, mockSchedules);

  const result1 = await getSpacedRepetitionSchedules(false);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/progress\/spaced-repetition\?include_unreviewed_active=false$/);
  assert.deepEqual(result1, mockSchedules);

  stubFetchOnce(200, mockSchedules);
  const result2 = await getSpacedRepetitionSchedules({ includeUnreviewedActive: true });
  assert.equal(calls.length, 2);
  assert.match(calls[1].url, /\/api\/v1\/progress\/spaced-repetition\?include_unreviewed_active=true$/);
  assert.deepEqual(result2, mockSchedules);
});

test("getProgressRecommendations formats optional limit query and credentials", async () => {
  const mockRecs = [
    {
      id: "sr:doc-1",
      priority: 1,
      type: "spaced_review",
    },
  ];
  stubFetchOnce(200, mockRecs);

  const result = await getProgressRecommendations(5);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/progress\/recommendations\?limit=5$/);
  assert.deepEqual(result, mockRecs);

  stubFetchOnce(200, mockRecs);
  await getProgressRecommendations();
  assert.equal(calls.length, 2);
  assert.match(calls[1].url, /\/api\/v1\/progress\/recommendations$/);
});

test("Progress API methods throw descriptive errors when response is not ok", async () => {
  stubFetchOnce(500, { detail: "Internal Server Error" });

  await assert.rejects(
    () => getProgressSummary(),
    (err) => {
      assert.equal(err.message, "Internal Server Error");
      return true;
    }
  );

  // When no body or empty JSON is returned, fallback is used
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => {
      throw new Error("Invalid json");
    },
  });

  await assert.rejects(
    () => getProgressTopics(),
    (err) => {
      assert.match(err.message, /Could not load topic mastery \(status 503\)/);
      return true;
    }
  );
});
