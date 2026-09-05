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
