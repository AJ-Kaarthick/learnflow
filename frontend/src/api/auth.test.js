import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { logout, signin, signup } from "./auth.js";

// This project's frontend test suite is plain `node --test`, with no
// DOM/browser environment (see utils/persistence.test.js's own note
// on the same constraint) -- but Node's built-in global `fetch` is
// still just a function, so it can be swapped out for a deterministic
// stub for the duration of each test, the same way persistence.test.js
// polyfills `window.localStorage` to exercise code that would
// otherwise need a real browser. This lets api/auth.js's actual
// request-shaping and response-parsing logic run for real, against a
// scripted response, instead of only being reachable through a live
// backend or a rendered component (which this suite can't do either
// -- see documentChip.test.js).

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

// --- signup -----------------------------------------------------------

test("signup posts to /api/v1/auth/signup with credentials included and the email/password body", async () => {
  stubFetchOnce(201, { type: "user", id: "user-1", email: "alice@example.com" });

  const identity = await signup("alice@example.com", "correct-horse");

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/auth\/signup$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    email: "alice@example.com",
    password: "correct-horse",
  });
  assert.deepEqual(identity, { type: "user", id: "user-1", email: "alice@example.com" });
});

test("signup rejects with the backend's detail message on a duplicate-account (409) response", async () => {
  stubFetchOnce(409, { detail: "An account with this email already exists." });

  await assert.rejects(
    () => signup("alice@example.com", "correct-horse"),
    (error) => error.message === "An account with this email already exists."
  );
});

test("signup falls back to a generic message when the error response has no detail", async () => {
  stubFetchOnce(500, {});

  await assert.rejects(
    () => signup("alice@example.com", "correct-horse"),
    (error) => error.message === "Could not sign up (status 500)"
  );
});

test("signup converts FastAPI's structured 422 validation-error shape into a plain, readable message (regression: this used to render as \"[object Object]\")", async () => {
  // This is the real shape FastAPI/pydantic sends for a 422 -- `detail`
  // is an array of objects, not a string. Manual QA on the first
  // Phase 2 pass found this reaching the UI unhandled; see
  // parseErrorDetail's docstring in auth.js for the full story.
  stubFetchOnce(422, {
    detail: [
      {
        type: "value_error",
        loc: ["body", "email"],
        msg: "Value error, Please enter a valid email address.",
        input: "test@gmail",
      },
    ],
  });

  await assert.rejects(
    () => signup("test@gmail", "Password1!"),
    (error) => {
      assert.equal(error.message, "Please enter a valid email address.");
      assert.doesNotMatch(error.message, /\[object Object\]/);
      assert.doesNotMatch(error.message, /^Value error,/);
      return true;
    }
  );
});

test("signup joins multiple structured validation errors (e.g. bad email and weak password at once) into one readable message", async () => {
  stubFetchOnce(422, {
    detail: [
      { type: "value_error", loc: ["body", "email"], msg: "Value error, Please enter a valid email address." },
      {
        type: "value_error",
        loc: ["body", "password"],
        msg: "Value error, Password must be at least 8 characters and include an uppercase letter, a lowercase letter, a number, and a special character.",
      },
    ],
  });

  await assert.rejects(() => signup("test@gmail", "11111111"), (error) => {
    assert.match(error.message, /Please enter a valid email address\./);
    assert.match(error.message, /Password must be at least 8 characters/);
    assert.doesNotMatch(error.message, /\[object Object\]/);
    return true;
  });
});

// --- signin -----------------------------------------------------------

test("signin posts to /api/v1/auth/signin with credentials included and the email/password body", async () => {
  stubFetchOnce(200, { type: "user", id: "user-2", email: "bob@example.com" });

  const identity = await signin("bob@example.com", "correct-horse");

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/auth\/signin$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(identity, { type: "user", id: "user-2", email: "bob@example.com" });
});

test("signin rejects with the backend's generic invalid-credentials message on a 401", async () => {
  stubFetchOnce(401, { detail: "Invalid email or password." });

  await assert.rejects(
    () => signin("bob@example.com", "wrong-password"),
    (error) => error.message === "Invalid email or password."
  );
});

// --- logout -----------------------------------------------------------

test("logout posts to /api/v1/auth/logout with credentials included and resolves with no value on success", async () => {
  stubFetchOnce(204, null);

  const result = await logout();

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/auth\/logout$/);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.credentials, "include");
  assert.equal(result, undefined);
});

test("logout rejects when the backend call fails", async () => {
  stubFetchOnce(500, {});

  await assert.rejects(() => logout(), (error) => error.message === "Could not log out (status 500)");
});
