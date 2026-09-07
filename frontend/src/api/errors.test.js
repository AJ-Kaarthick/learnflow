import assert from "node:assert/strict";
import { test } from "node:test";
import { GuestLimitError, isGuestLimitError, parseErrorResponse } from "./errors.js";

// Same technique as auth.test.js's own stubFetchOnce -- a fake
// Response object with just enough shape (`.json()`) for
// parseErrorResponse to work with, no real network or DOM involved.
function fakeResponse(body) {
  return { json: async () => body };
}

// --- string detail --------------------------------------------------

test("parseErrorResponse turns a plain string detail into an Error with that message", async () => {
  const error = await parseErrorResponse(fakeResponse({ detail: "Something went wrong." }), "fallback");

  assert.ok(error instanceof Error);
  assert.equal(error.message, "Something went wrong.");
});

test("parseErrorResponse falls back when detail is an empty/whitespace-only string", async () => {
  const error = await parseErrorResponse(fakeResponse({ detail: "   " }), "fallback message");

  assert.equal(error.message, "fallback message");
});

// --- no detail / unreadable body -------------------------------------

test("parseErrorResponse falls back when there is no detail at all", async () => {
  const error = await parseErrorResponse(fakeResponse({}), "fallback message");

  assert.equal(error.message, "fallback message");
});

test("parseErrorResponse falls back when the body isn't valid JSON", async () => {
  const response = { json: async () => { throw new Error("not JSON"); } };

  const error = await parseErrorResponse(response, "fallback message");

  assert.equal(error.message, "fallback message");
});

// --- FastAPI/pydantic 422 array shape ---------------------------------

test("parseErrorResponse converts a pydantic-style validation-error array into a readable message (regression: this used to render as \"[object Object]\")", async () => {
  const response = fakeResponse({
    detail: [
      {
        type: "value_error",
        loc: ["body", "email"],
        msg: "Value error, Please enter a valid email address.",
      },
    ],
  });

  const error = await parseErrorResponse(response, "fallback");

  assert.equal(error.message, "Please enter a valid email address.");
  assert.doesNotMatch(error.message, /\[object Object\]/);
  assert.doesNotMatch(error.message, /^Value error,/);
});

test("parseErrorResponse joins multiple validation-error entries into one message", async () => {
  const response = fakeResponse({
    detail: [
      { msg: "Value error, Please enter a valid email address." },
      { msg: "Value error, Password is too weak." },
    ],
  });

  const error = await parseErrorResponse(response, "fallback");

  assert.match(error.message, /Please enter a valid email address\./);
  assert.match(error.message, /Password is too weak\./);
});

test("parseErrorResponse falls back for an empty detail array", async () => {
  const error = await parseErrorResponse(fakeResponse({ detail: [] }), "fallback message");

  assert.equal(error.message, "fallback message");
});

// --- V3 Milestone 1 Phase 3: guest-limit object shape -------------------

test("parseErrorResponse turns a guest-limit detail object into a GuestLimitError, not a plain Error", async () => {
  const response = fakeResponse({
    detail: {
      code: "guest_limit_reached",
      limit_type: "document_upload",
      limit: 3,
      used: 3,
      message: "Guests can upload documents up to 3 times. Sign up for a free account to keep going.",
    },
  });

  const error = await parseErrorResponse(response, "fallback");

  assert.ok(error instanceof GuestLimitError);
  assert.equal(error.code, "guest_limit_reached");
  assert.equal(error.limitType, "document_upload");
  assert.equal(error.limit, 3);
  assert.equal(error.used, 3);
  assert.equal(
    error.message,
    "Guests can upload documents up to 3 times. Sign up for a free account to keep going."
  );
  assert.doesNotMatch(error.message, /\[object Object\]/);
});

test("isGuestLimitError is true for a parsed guest-limit error and false for everything else", async () => {
  const guestLimitError = await parseErrorResponse(
    fakeResponse({
      detail: {
        code: "guest_limit_reached",
        limit_type: "chat_message",
        limit: 15,
        used: 15,
        message: "Guests can send chat messages up to 15 times.",
      },
    }),
    "fallback"
  );
  const plainError = await parseErrorResponse(fakeResponse({ detail: "Not found." }), "fallback");

  assert.equal(isGuestLimitError(guestLimitError), true);
  assert.equal(isGuestLimitError(plainError), false);
  assert.equal(isGuestLimitError(null), false);
  assert.equal(isGuestLimitError(undefined), false);
  assert.equal(isGuestLimitError(new Error("plain")), false);
});

// --- Any other unrecognized object shape --------------------------------

test("parseErrorResponse never hands an unrecognized object straight to Error (regression: \"[object Object]\")", async () => {
  const response = fakeResponse({ detail: { some: "unexpected", shape: true } });

  const error = await parseErrorResponse(response, "fallback message");

  assert.equal(error.message, "fallback message");
  assert.doesNotMatch(error.message, /\[object Object\]/);
});

test("parseErrorResponse uses an unrecognized object's own message field when present", async () => {
  const response = fakeResponse({ detail: { message: "A specific, human-readable problem." } });

  const error = await parseErrorResponse(response, "fallback message");

  assert.equal(error.message, "A specific, human-readable problem.");
});
