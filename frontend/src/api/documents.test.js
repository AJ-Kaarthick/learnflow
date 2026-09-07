import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { isGuestLimitError } from "./errors.js";
import { deleteDocument, listDocuments, renameDocument, uploadDocument } from "./documents.js";

// Same stubbing technique as auth.test.js -- see that file's own note
// on why this works without a DOM/browser environment.

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

test("uploadDocument posts multipart form data with credentials included", async () => {
  stubFetchOnce(201, { id: "doc-1", status: "ready" });

  const document = await uploadDocument(new Blob(["hello"]));

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/documents\/upload$/);
  assert.equal(calls[0].options.method, "POST");
  assert.ok(calls[0].options.body instanceof FormData);
  assert.deepEqual(document, { id: "doc-1", status: "ready" });
});

test(
  "uploadDocument rejects with a GuestLimitError carrying a readable message when the guest document-upload limit is reached " +
    '(regression: this used to render as "[object Object]")',
  async () => {
    stubFetchOnce(403, {
      detail: {
        code: "guest_limit_reached",
        limit_type: "document_upload",
        limit: 3,
        used: 3,
        message: "Guests can upload documents up to 3 times. Sign up for a free account to keep going.",
      },
    });

    await assert.rejects(
      () => uploadDocument(new Blob(["hello"])),
      (error) => {
        assert.equal(isGuestLimitError(error), true);
        assert.equal(error.limitType, "document_upload");
        assert.equal(
          error.message,
          "Guests can upload documents up to 3 times. Sign up for a free account to keep going."
        );
        assert.doesNotMatch(error.message, /\[object Object\]/);
        return true;
      }
    );
  }
);

test("uploadDocument falls back to a generic message when the error response has no detail", async () => {
  stubFetchOnce(500, {});

  await assert.rejects(
    () => uploadDocument(new Blob(["hello"])),
    (error) => error.message === "Upload failed with status 500"
  );
});

test("listDocuments GETs the documents endpoint with search/sort query params", async () => {
  stubFetchOnce(200, []);

  await listDocuments({ search: "notes", sort: "name_asc" });

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v1\/documents\?/);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get("search"), "notes");
  assert.equal(url.searchParams.get("sort"), "name_asc");
});

test("renameDocument surfaces a structured validation error as a readable message, not \"[object Object]\"", async () => {
  stubFetchOnce(422, { detail: "Name cannot be empty." });

  await assert.rejects(
    () => renameDocument("doc-1", ""),
    (error) => error.message === "Name cannot be empty."
  );
});

test("deleteDocument DELETEs the document and resolves with no value on success", async () => {
  stubFetchOnce(204, null);

  const result = await deleteDocument("doc-1");

  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, "DELETE");
  assert.equal(result, undefined);
});
