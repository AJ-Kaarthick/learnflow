import assert from "node:assert/strict";
import { test } from "node:test";
import {
  EMAIL_FORMAT_ERROR,
  PASSWORD_REQUIREMENTS_MESSAGE,
  getEmailFormatError,
  getPasswordStrengthError,
  isValidEmailFormat,
  meetsPasswordRequirements,
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
