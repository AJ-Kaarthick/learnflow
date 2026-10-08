import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { isGuestLimitError } from "./errors.js";
import {
  completeRevisionSession,
  createRevisionSession,
  getRevisionSession,
  listRevisionSessions,
  submitRevisionAttempt,
} from "./revision.js";

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

test("createRevisionSession sends POST with valid body and credentials", async () => {
  const mockSession = {
    id: "rev-sess-1",
    title: "Cell Biology Practice",
    status: "in_progress",
    total_questions: 5,
    questions: [],
    documents: [],
  };

  stubFetchOnce(201, mockSession);

  const result = await createRevisionSession({
    documentIds: ["doc-1", "doc-2"],
    title: "Cell Biology Practice",
    difficulty: "intermediate",
    mode: "practice",
    questionType: "multiple_choice",
    questionCount: 5,
  });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/revision\/sessions$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");

  const sentBody = JSON.parse(calls[0].options.body);
  assert.deepEqual(sentBody, {
    document_ids: ["doc-1", "doc-2"],
    title: "Cell Biology Practice",
    difficulty: "intermediate",
    mode: "practice",
    question_type: "multiple_choice",
    question_count: 5,
  });
  assert.deepEqual(result, mockSession);
});

test("createRevisionSession omits empty title and applies defaults", async () => {
  stubFetchOnce(201, { id: "rev-sess-2" });

  await createRevisionSession({
    documentIds: ["doc-1"],
  });

  assert.equal(calls.length, 1);
  const sentBody = JSON.parse(calls[0].options.body);
  assert.deepEqual(sentBody, {
    document_ids: ["doc-1"],
    difficulty: "intermediate",
    mode: "practice",
    question_type: "multiple_choice",
    question_count: 5,
  });
  assert.equal(sentBody.title, undefined);
});

test("createRevisionSession accepts snake_case options from buildCreateSessionPayload without omitting document_ids", async () => {
  stubFetchOnce(201, { id: "rev-sess-snake" });

  await createRevisionSession({
    document_ids: ["doc-a", "doc-b"],
    difficulty: "advanced",
    mode: "quiz",
    question_type: "open_ended",
    question_count: 8,
    title: "Exam Prep",
  });

  assert.equal(calls.length, 1);
  const sentBody = JSON.parse(calls[0].options.body);
  assert.deepEqual(sentBody, {
    document_ids: ["doc-a", "doc-b"],
    difficulty: "advanced",
    mode: "quiz",
    question_type: "open_ended",
    question_count: 8,
    title: "Exam Prep",
  });

  // Verify that document_ids is an array with items, never undefined/missing
  assert.ok(Array.isArray(sentBody.document_ids));
  assert.equal(sentBody.document_ids.length, 2);
  assert.equal(Object.prototype.hasOwnProperty.call(sentBody, "document_ids"), true);
});

test("createRevisionSession throws GuestLimitError on 403 guest limit response", async () => {
  stubFetchOnce(403, {
    detail: {
      code: "guest_limit_reached",
      limit_type: "ai_generation",
      limit: 5,
      used: 5,
      message: "Guests can generate AI study material up to 5 times. Sign up for a free account to keep going.",
    },
  });

  await assert.rejects(
    () => createRevisionSession({ documentIds: ["doc-1"] }),
    (error) => {
      assert.ok(isGuestLimitError(error));
      assert.equal(error.code, "guest_limit_reached");
      assert.match(error.message, /Guests can generate AI study material/);
      return true;
    }
  );
});

test("createRevisionSession maps 502 to friendly AI error message", async () => {
  stubFetchOnce(502, { detail: "Upstream LLM timeout" });

  await assert.rejects(
    () => createRevisionSession({ documentIds: ["doc-1"] }),
    (error) => {
      assert.equal(
        error.message,
        "The AI couldn't generate revision questions right now. Please try again in a moment."
      );
      return true;
    }
  );
});

test("createRevisionSession propagates 400 validation error", async () => {
  stubFetchOnce(400, { detail: "Document is not ready for revision." });

  await assert.rejects(
    () => createRevisionSession({ documentIds: ["doc-unready"] }),
    (error) => {
      assert.match(error.message, /Document is not ready for revision/);
      return true;
    }
  );
});

test("listRevisionSessions sends GET with credentials", async () => {
  const mockSessions = [
    { id: "rev-1", title: "Session 1", total_questions: 3 },
    { id: "rev-2", title: "Session 2", total_questions: 5 },
  ];

  stubFetchOnce(200, mockSessions);

  const result = await listRevisionSessions();
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/revision\/sessions$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockSessions);
});

test("getRevisionSession sends GET for session ID with credentials", async () => {
  const mockDetail = { id: "rev-123", title: "Detail Session", questions: [] };
  stubFetchOnce(200, mockDetail);

  const result = await getRevisionSession("rev-123");
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/revision\/sessions\/rev-123$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockDetail);
});

test("getRevisionSession throws on 404 not found", async () => {
  stubFetchOnce(404, { detail: "Revision session not found." });

  await assert.rejects(
    () => getRevisionSession("rev-missing"),
    (error) => {
      assert.match(error.message, /Revision session not found/);
      return true;
    }
  );
});

test("submitRevisionAttempt sends POST with submitted_answer and credentials", async () => {
  const mockAttempt = {
    id: "att-1",
    question_id: "q-1",
    session_id: "rev-1",
    attempt_number: 1,
    submitted_answer: "B",
    is_correct: true,
    score: 1.0,
    feedback: "Correct answer!",
    explanation: "Option B is correct.",
    correct_answer: "B",
  };

  stubFetchOnce(201, mockAttempt);

  const result = await submitRevisionAttempt("rev-1", "q-1", "B");
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/revision\/sessions\/rev-1\/questions\/q-1\/attempts$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(JSON.parse(calls[0].options.body), { submitted_answer: "B" });
  assert.deepEqual(result, mockAttempt);
});

test("submitRevisionAttempt throws GuestLimitError on 403 quota exhaustion", async () => {
  stubFetchOnce(403, {
    detail: {
      code: "guest_limit_reached",
      limit_type: "ai_generation",
      limit: 5,
      used: 5,
      message: "Guests can generate AI study material up to 5 times. Sign up for a free account to keep going.",
    },
  });

  await assert.rejects(
    () => submitRevisionAttempt("rev-1", "q-1", "My detailed answer"),
    (error) => {
      assert.ok(isGuestLimitError(error));
      assert.equal(error.code, "guest_limit_reached");
      return true;
    }
  );
});

test("submitRevisionAttempt maps 502 to friendly evaluation error", async () => {
  stubFetchOnce(502, { detail: "Provider down" });

  await assert.rejects(
    () => submitRevisionAttempt("rev-1", "q-1", "My answer"),
    (error) => {
      assert.equal(
        error.message,
        "The AI couldn't evaluate your answer right now. Please try again in a moment."
      );
      return true;
    }
  );
});

test("completeRevisionSession sends POST to /complete endpoint", async () => {
  const mockCompleted = {
    id: "rev-1",
    status: "completed",
    score: 0.85,
    completed_at: "2026-10-06T12:00:00Z",
  };

  stubFetchOnce(200, mockCompleted);

  const result = await completeRevisionSession("rev-1");
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/revision\/sessions\/rev-1\/complete$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(result, mockCompleted);
});

test("completeRevisionSession propagates error when already completed", async () => {
  stubFetchOnce(400, { detail: "Cannot complete a revision session that is already completed." });

  await assert.rejects(
    () => completeRevisionSession("rev-1"),
    (error) => {
      assert.match(error.message, /Cannot complete a revision session that is already completed/);
      return true;
    }
  );
});
