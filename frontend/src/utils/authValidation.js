/**
 * Client-side mirror of the account-authentication validation rules
 * enforced server-side in backend/app/schemas/auth.py (V3 Milestone 1
 * Phase 2, tightened after manual QA found "test@gmail" and
 * "11111111" both getting further than they should). Kept as pure,
 * dependency-free functions -- same "extracted so it's directly
 * testable under this project's DOM-less `node --test` suite"
 * reasoning as utils/authState.js -- and used by AuthPanel.jsx to
 * reject obviously-invalid input before it ever reaches the network,
 * with the same wording the backend would otherwise reject it with.
 *
 * This is a deliberate duplication, not a shared package: the
 * frontend and backend are two different languages with no shared
 * module boundary in this project, and re-validating on the frontend
 * is only ever a UX nicety (faster feedback, one fewer round trip) --
 * the backend's own copy of these rules (schemas/auth.py) is what
 * actually enforces them; nothing about account security depends on
 * this file agreeing with it, but the *wording* below is kept
 * word-for-word identical to schemas/auth.py's messages on purpose,
 * so a person never sees a different sentence depending on whether
 * their mistake was caught here or by the server's response.
 */

// Mirrors backend/app/schemas/auth.py's `_EMAIL_PATTERN` exactly: one
// `@`, something on each side, and a literal `.` somewhere in the
// domain part -- loose on purpose (not full RFC 5322), just enough to
// catch obviously-incomplete input like "test@gmail" (no domain
// suffix) without pretending to verify the address is deliverable.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const EMAIL_FORMAT_ERROR = "Please enter a valid email address.";

// Mirrors backend/app/schemas/auth.py's MIN_PASSWORD_LENGTH /
// MAX_PASSWORD_LENGTH and _PASSWORD_REQUIREMENTS_MESSAGE.
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 72;

export const PASSWORD_REQUIREMENTS_MESSAGE =
  "Password must be at least 8 characters and include an uppercase letter, a lowercase letter, a number, and a special character.";

// Mirrors backend's use of Python's `string.punctuation` as "any
// special character" -- the same fixed ASCII punctuation set, spelled
// out here since JS has no equivalent standard-library constant to
// import.
const SPECIAL_CHARACTER_PATTERN = /[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/;

/** True if `email` is at least loosely shaped like a real address. */
export function isValidEmailFormat(email) {
  return EMAIL_PATTERN.test((email || "").trim());
}

/**
 * Returns the friendly error to show for `email`, or null if it's
 * fine. Kept as its own function (rather than inlining the boolean
 * check at each call site) so AuthPanel.jsx's validation and its
 * error message stay defined in exactly one place.
 */
export function getEmailFormatError(email) {
  return isValidEmailFormat(email) ? null : EMAIL_FORMAT_ERROR;
}

/** True if `password` satisfies every rule in the policy. */
export function meetsPasswordRequirements(password) {
  const value = password || "";
  return (
    value.length >= MIN_PASSWORD_LENGTH &&
    value.length <= MAX_PASSWORD_LENGTH &&
    /[A-Z]/.test(value) &&
    /[a-z]/.test(value) &&
    /[0-9]/.test(value) &&
    SPECIAL_CHARACTER_PATTERN.test(value)
  );
}

/**
 * Returns the friendly error to show for `password`, or null if it's
 * fine. A single consolidated message for any failing rule (matching
 * the backend's own choice, see schemas/auth.py's
 * _validate_password_strength docstring for why) -- a form asking
 * someone to fix "at least one of five things" is better served by
 * one clear sentence of *all* the requirements than by only telling
 * them the first rule they happened to violate.
 */
export function getPasswordStrengthError(password) {
  return meetsPasswordRequirements(password) ? null : PASSWORD_REQUIREMENTS_MESSAGE;
}

// --- Password confirmation (sign-up modal, V3 Milestone 1 Phase 3) -----
//
// Purely a client-side UX nicety, same caveat as the rest of this
// file: nothing about account security depends on the two fields
// agreeing here, since the backend only ever receives a single
// `password` value (see api/auth.js's signup) -- this just catches a
// typo before it round-trips to the server as a created account the
// person can't immediately re-enter the password for.

export const PASSWORD_CONFIRMATION_MISMATCH_ERROR = "Passwords do not match.";

/** True if `password` and `confirmPassword` are exactly equal. */
export function passwordsMatch(password, confirmPassword) {
  return (password || "") === (confirmPassword || "");
}

/**
 * Returns the friendly error to show when the confirm-password field
 * doesn't match `password`, or null if it does. Deliberately flags an
 * empty `confirmPassword` against a non-empty `password` too (rather
 * than treating "not yet typed" as "not yet wrong") -- AuthPanel.jsx
 * only calls this at submit time, by which point the field should no
 * longer be blank.
 */
export function getPasswordConfirmationError(password, confirmPassword) {
  return passwordsMatch(password, confirmPassword) ? null : PASSWORD_CONFIRMATION_MISMATCH_ERROR;
}

// --- Password visibility toggle (sign-in + sign-up password fields) ----
//
// Extracted as pure functions -- rather than inlined as a ternary at
// each call site -- for the same "directly testable under this
// project's DOM-less `node --test` suite" reason as everything else
// in this file, since AuthPanel.jsx itself has no test file (see
// AuthContext.jsx's own comment on why components/context aren't
// unit-tested here).

/** The `<input type="...">` to use for a password field given whether it's currently shown in the clear. */
export function getPasswordInputType(isVisible) {
  return isVisible ? "text" : "password";
}

/** The `aria-label` for the eye toggle button, describing the action tapping it will perform next. */
export function getPasswordVisibilityToggleAriaLabel(isVisible, fieldLabel = "password") {
  return isVisible ? `Hide ${fieldLabel}` : `Show ${fieldLabel}`;
}
