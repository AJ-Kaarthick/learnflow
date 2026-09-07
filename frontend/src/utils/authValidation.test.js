import assert from "node:assert/strict";
import { test } from "node:test";
import {
  EMAIL_FORMAT_ERROR,
  PASSWORD_CONFIRMATION_MISMATCH_ERROR,
  PASSWORD_REQUIREMENTS_MESSAGE,
  getEmailFormatError,
  getPasswordConfirmationError,
  getPasswordInputType,
  getPasswordStrengthError,
  getPasswordVisibilityToggleAriaLabel,
  isValidEmailFormat,
  meetsPasswordRequirements,
  passwordsMatch,
} from "./authValidation.js";

// V3 Milestone 1 Phase 2 fix: manual QA on the first Phase 2 pass
// found "test@gmail" / "oidu@text" reaching account creation, and a
// password like "11111111" being accepted outright. These tests pin
// down the client-side mirror of the (now-tightened) backend rules in
// backend/app/schemas/auth.py -- see authValidation.js's own comment
// for why this is a deliberate duplication rather than shared code.

// --- Email format ------------------------------------------------------

test("isValidEmailFormat accepts an ordinary address", () => {
  assert.equal(isValidEmailFormat("alice@example.com"), true);
});

test("isValidEmailFormat rejects an address with no domain suffix (the exact QA-reported bug)", () => {
  assert.equal(isValidEmailFormat("test@gmail"), false);
  assert.equal(isValidEmailFormat("oidu@text"), false);
});

test("isValidEmailFormat rejects a string with no @ at all", () => {
  assert.equal(isValidEmailFormat("not-an-email"), false);
});

test("isValidEmailFormat rejects an empty or missing value without throwing", () => {
  assert.equal(isValidEmailFormat(""), false);
  assert.equal(isValidEmailFormat(undefined), false);
});

test("isValidEmailFormat tolerates surrounding whitespace", () => {
  assert.equal(isValidEmailFormat("  alice@example.com  "), true);
});

test("getEmailFormatError returns null for a valid email and the friendly message otherwise", () => {
  assert.equal(getEmailFormatError("alice@example.com"), null);
  assert.equal(getEmailFormatError("test@gmail"), EMAIL_FORMAT_ERROR);
  assert.equal(getEmailFormatError("test@gmail"), "Please enter a valid email address.");
});

// --- Password strength --------------------------------------------------

test("meetsPasswordRequirements accepts a password satisfying every rule", () => {
  assert.equal(meetsPasswordRequirements("Password1!"), true);
});

test("meetsPasswordRequirements rejects the exact QA-reported weak password (digits only)", () => {
  assert.equal(meetsPasswordRequirements("11111111"), false);
});

test("meetsPasswordRequirements rejects a password missing an uppercase letter", () => {
  assert.equal(meetsPasswordRequirements("lowercase1!"), false);
});

test("meetsPasswordRequirements rejects a password missing a lowercase letter", () => {
  assert.equal(meetsPasswordRequirements("UPPERCASE1!"), false);
});

test("meetsPasswordRequirements rejects a password missing a number", () => {
  assert.equal(meetsPasswordRequirements("NoNumberHere!"), false);
});

test("meetsPasswordRequirements rejects a password missing a special character", () => {
  assert.equal(meetsPasswordRequirements("NoSpecial123"), false);
});

test("meetsPasswordRequirements rejects a password shorter than 8 characters", () => {
  assert.equal(meetsPasswordRequirements("Sh0rt!"), false);
});

test("meetsPasswordRequirements rejects an empty or missing value without throwing", () => {
  assert.equal(meetsPasswordRequirements(""), false);
  assert.equal(meetsPasswordRequirements(undefined), false);
});

test("getPasswordStrengthError returns null for a strong password and the requirements message otherwise", () => {
  assert.equal(getPasswordStrengthError("Password1!"), null);
  assert.equal(getPasswordStrengthError("11111111"), PASSWORD_REQUIREMENTS_MESSAGE);
});

test("PASSWORD_REQUIREMENTS_MESSAGE matches the wording backend/app/schemas/auth.py raises, word-for-word", () => {
  // Not a functional test of authValidation.js itself -- a regression
  // guard that the frontend guidance text and the backend's rejection
  // message can never silently drift apart (see authValidation.js's
  // module docstring for why that matters).
  assert.equal(
    PASSWORD_REQUIREMENTS_MESSAGE,
    "Password must be at least 8 characters and include an uppercase letter, a lowercase letter, a number, and a special character."
  );
});

// --- Password confirmation (sign-up modal, V3 Milestone 1 Phase 3) -----
// Pins down the client-side match check backing the new "Confirm
// password" field in AuthPanel.jsx. This is a pure-function test, not
// a rendered-component test, matching this project's established
// convention of only unit-testing plain functions and leaving
// components/context untested (see AuthContext.jsx's comment on why)
// -- AuthPanel.jsx wires its confirm-password field, its mismatch
// error, and its eye-toggle buttons directly to these same functions,
// so exercising them here is exercising the exact logic that decides
// whether a signup submission is allowed to proceed.

test("passwordsMatch returns true for identical values", () => {
  assert.equal(passwordsMatch("Password1!", "Password1!"), true);
});

test("passwordsMatch returns false when the values differ", () => {
  assert.equal(passwordsMatch("Password1!", "Password2!"), false);
});

test("passwordsMatch treats a missing value as an empty string without throwing", () => {
  assert.equal(passwordsMatch(undefined, undefined), true);
  assert.equal(passwordsMatch("Password1!", undefined), false);
  assert.equal(passwordsMatch(undefined, "Password1!"), false);
});

test("getPasswordConfirmationError returns null when the passwords match (signup may proceed)", () => {
  assert.equal(getPasswordConfirmationError("Password1!", "Password1!"), null);
});

test("getPasswordConfirmationError returns the mismatch message when the passwords differ", () => {
  assert.equal(getPasswordConfirmationError("Password1!", "Password1"), PASSWORD_CONFIRMATION_MISMATCH_ERROR);
  assert.equal(getPasswordConfirmationError("Password1!", "Password1"), "Passwords do not match.");
});

test("getPasswordConfirmationError flags a blank confirm-password field against a non-empty password", () => {
  assert.equal(getPasswordConfirmationError("Password1!", ""), PASSWORD_CONFIRMATION_MISMATCH_ERROR);
});

// --- Password visibility toggle (sign-in + sign-up password fields) ----

test("getPasswordInputType returns 'password' when hidden and 'text' when visible", () => {
  assert.equal(getPasswordInputType(false), "password");
  assert.equal(getPasswordInputType(true), "text");
});

test("getPasswordVisibilityToggleAriaLabel describes the action tapping the eye icon will perform next", () => {
  assert.equal(getPasswordVisibilityToggleAriaLabel(false, "password"), "Show password");
  assert.equal(getPasswordVisibilityToggleAriaLabel(true, "password"), "Hide password");
});

test("getPasswordVisibilityToggleAriaLabel works for the confirm-password field's own label too", () => {
  assert.equal(getPasswordVisibilityToggleAriaLabel(false, "confirm password"), "Show confirm password");
  assert.equal(getPasswordVisibilityToggleAriaLabel(true, "confirm password"), "Hide confirm password");
});
