import assert from "node:assert/strict";
import { test } from "node:test";
import {
  INITIAL_AUTH_STATE,
  authStateAfterAuthError,
  authStateAfterRestoreFailure,
  authStateClearingError,
  authStateFromIdentity,
} from "./authState.js";

// Pure state-transition coverage for AuthContext.jsx (V3 Milestone 1
// Phase 2) -- see authState.js's own docstring for why this logic is
// extracted into a plain module: AuthContext itself can't be rendered
// in this project's `node --test` frontend suite (no DOM/JSX
// pipeline), but the actual decision ("given this identity/error,
// what should state become?") has no React or fetch dependency of its
// own.

test("INITIAL_AUTH_STATE starts as loading, with no identity or error", () => {
  assert.deepEqual(INITIAL_AUTH_STATE, { status: "loading", identity: null, error: null });
});

// --- authStateFromIdentity: initial restore, signup, signin, post-logout ---

test("authStateFromIdentity sets status to ready and clears any prior error, for a guest identity", () => {
  const guestIdentity = { type: "guest", id: "guest-1", email: null };

  const next = authStateFromIdentity(guestIdentity);

  assert.equal(next.status, "ready");
  assert.deepEqual(next.identity, guestIdentity);
  assert.equal(next.error, null);
});

test("authStateFromIdentity sets status to ready for an authenticated (user) identity", () => {
  const userIdentity = { type: "user", id: "user-1", email: "alice@example.com" };

  const next = authStateFromIdentity(userIdentity);

  assert.equal(next.status, "ready");
  assert.deepEqual(next.identity, userIdentity);
  assert.equal(next.error, null);
});

test("authStateFromIdentity clears an error that was showing before (e.g. a successful signin after a prior failed attempt)", () => {
  const previouslyErrored = { status: "ready", identity: null, error: "Invalid email or password." };
  const userIdentity = { type: "user", id: "user-2", email: "bob@example.com" };

  // authStateFromIdentity doesn't take previous state -- it always
  // produces a full ready state from scratch, discarding whatever
  // error was there before, which is exactly the guarantee this test
  // checks by starting from an errored-looking state and confirming
  // the result has none.
  const next = authStateFromIdentity(userIdentity);
  void previouslyErrored;

  assert.equal(next.error, null);
});

// --- authStateAfterRestoreFailure: initial GET /identity/me itself fails ---

test("authStateAfterRestoreFailure sets status to error and clears identity", () => {
  const next = authStateAfterRestoreFailure(new Error("Network request failed"));

  assert.equal(next.status, "error");
  assert.equal(next.identity, null);
  assert.equal(next.error, "Network request failed");
});

test("authStateAfterRestoreFailure falls back to a generic message when the error has none", () => {
  const next = authStateAfterRestoreFailure(new Error());

  assert.equal(next.error, "Could not load your account state.");
});

test("authStateAfterRestoreFailure falls back to a generic message when called with no error at all", () => {
  const next = authStateAfterRestoreFailure(undefined);

  assert.equal(next.error, "Could not load your account state.");
});

// --- authStateAfterAuthError: a failed signup/signin attempt --------------

test("authStateAfterAuthError sets the error message but leaves status and identity untouched (regression guard: a failed login must not log out an already-authenticated session)", () => {
  const alreadySignedIn = {
    status: "ready",
    identity: { type: "user", id: "user-3", email: "carol@example.com" },
    error: null,
  };

  const next = authStateAfterAuthError(alreadySignedIn, new Error("Invalid email or password."));

  assert.equal(next.status, "ready");
  assert.deepEqual(next.identity, alreadySignedIn.identity);
  assert.equal(next.error, "Invalid email or password.");
});

test("authStateAfterAuthError leaves a guest identity as-is after a failed signin attempt", () => {
  const guestState = { status: "ready", identity: { type: "guest", id: "guest-2", email: null }, error: null };

  const next = authStateAfterAuthError(guestState, new Error("Invalid email or password."));

  assert.deepEqual(next.identity, guestState.identity);
  assert.equal(next.error, "Invalid email or password.");
});

test("authStateAfterAuthError falls back to a generic message when the error has none", () => {
  const state = { status: "ready", identity: null, error: null };

  const next = authStateAfterAuthError(state, new Error());

  assert.equal(next.error, "Something went wrong. Please try again.");
});

// --- authStateClearingError: switching between signin/signup forms --------

test("authStateClearingError removes a previous error without touching status or identity", () => {
  const erroredState = {
    status: "ready",
    identity: { type: "guest", id: "guest-3", email: null },
    error: "An account with this email already exists.",
  };

  const next = authStateClearingError(erroredState);

  assert.equal(next.error, null);
  assert.equal(next.status, "ready");
  assert.deepEqual(next.identity, erroredState.identity);
});

test("authStateClearingError is a no-op shape-wise when there was no error to clear", () => {
  const cleanState = { status: "ready", identity: { type: "guest", id: "guest-4", email: null }, error: null };

  const next = authStateClearingError(cleanState);

  assert.deepEqual(next, cleanState);
});
