import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { getIdentity } from "./identity.js";

// Same global-`fetch`-stub approach as api/auth.test.js -- see that
// file's comment for why this is the right way to exercise a thin
// api/*.js module in this project's DOM-less `node --test` suite.

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

test("getIdentity fetches /api/v1/identity/me with credentials included", async () => {
  stubFetchOnce(200, { type: "guest", id: "guest-1", email: null });

  const identity = await getIdentity();

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/identity\/me$/);
  assert.equal(calls[0].options.credentials, "include");
  assert.deepEqual(identity, { type: "guest", id: "guest-1", email: null });
});

test("getIdentity resolves an authenticated identity's email straight through, unmodified", async () => {
  stubFetchOnce(200, { type: "user", id: "user-1", email: "alice@example.com" });

  const identity = await getIdentity();

  assert.equal(identity.type, "user");
  assert.equal(identity.email, "alice@example.com");
});

test("getIdentity rejects when the backend call fails", async () => {
  stubFetchOnce(500, {});

  await assert.rejects(
    () => getIdentity(),
    (error) => error.message === "Could not resolve the current identity (status 500)"
  );
});
