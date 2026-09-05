/**
 * Pure state-shape helpers behind AuthContext.jsx (V3 Milestone 1
 * Phase 2). Extracted from the context/provider itself for the same
 * reason utils/conversationSelection.js and utils/documentUploadSync.js
 * are extracted from their pages/components: this project's frontend
 * test suite is plain `node --test` with no DOM/JSX pipeline (see
 * documentChip.test.js), so a React context provider can't be
 * rendered and asserted on directly -- but the actual decision it
 * makes ("given this identity/error, what should state become?") is
 * plain data-in, data-out logic with no React or fetch dependency of
 * its own, and is exactly what's worth guarding with a test.
 *
 * AuthContext's job on top of this module is thin: call an api/*.js
 * function, then hand whatever it got (or threw) to one of these to
 * decide the next state.
 */

// `status` is one of:
//   "loading"       -- identity hasn't been resolved yet (initial mount)
//   "ready"         -- `identity` reflects who the backend says this
//                      request is, guest or authenticated
//   "error"         -- the initial identity restore itself failed
//                      (e.g. backend unreachable) -- distinct from a
//                      failed signup/signin attempt, which never
//                      touches `status` (see authStateAfterAuthError)
//                      and leaves whatever identity was already
//                      showing untouched.
export const INITIAL_AUTH_STATE = { status: "loading", identity: null, error: null };

/**
 * The state to show once an Identity has been resolved or established
 * -- on initial mount (GET /identity/me), and after a successful
 * signup, signin, or post-logout re-resolution. All three are the
 * same shape (see schemas/identity.py's Identity: `type`, `id`,
 * `email`), so all three collapse to this one function.
 */
export function authStateFromIdentity(identity) {
  return { status: "ready", identity, error: null };
}

/**
 * The state to show when the *initial* identity restore fails (e.g.
 * the backend is unreachable on first load) -- distinct from a failed
 * signup/signin attempt (see authStateAfterAuthError below), which
 * shouldn't blank out whatever identity/UI was already showing.
 */
export function authStateAfterRestoreFailure(error) {
  return { status: "error", identity: null, error: error?.message || "Could not load your account state." };
}

/**
 * The state to show after a failed signup/signin attempt. Unlike
 * authStateAfterRestoreFailure, this deliberately keeps `status` and
 * `identity` exactly as they were -- a rejected login attempt doesn't
 * change who the browser is currently authenticated as (still a guest,
 * most likely), it just needs the form to show why the attempt
 * failed. Keeping this as its own function (rather than callers
 * hand-rolling `{ ...state, error }`) documents that "don't touch
 * identity/status here" as a checked contract, not just a convention
 * every call site has to remember.
 */
export function authStateAfterAuthError(previousState, error) {
  return { ...previousState, error: error?.message || "Something went wrong. Please try again." };
}

/**
 * Clears a previously-shown auth error without otherwise touching
 * state -- used when the person switches between the sign-in and
 * sign-up forms, or edits the form after a failed attempt, so a stale
 * error message doesn't linger once they're trying again.
 */
export function authStateClearingError(previousState) {
  return { ...previousState, error: null };
}
