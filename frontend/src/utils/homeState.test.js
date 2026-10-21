import assert from "node:assert/strict";
import { test } from "node:test";
import { ROUTES } from "../router/useHashRoute.js";
import {
  QUICK_ACTIONS,
  formatGreetingTitle,
  formatRecentDocumentDate,
  getGreetingSubtitle,
} from "./homeState.js";

// ---------------------------------------------------------------------------
// 1. formatGreetingTitle Tests
// ---------------------------------------------------------------------------
test("formatGreetingTitle formats user greeting with email prefix", () => {
  const user = { type: "user", id: "user-1", email: "student@example.com" };
  assert.equal(formatGreetingTitle(user), "Welcome, student");
  assert.equal(formatGreetingTitle(user, 9), "Good morning, student");
  assert.equal(formatGreetingTitle(user, 13), "Good afternoon, student");
  assert.equal(formatGreetingTitle(user, 21), "Good evening, student");
});

test("formatGreetingTitle formats guest greeting", () => {
  const guest = { type: "guest", id: "guest-1" };
  assert.equal(formatGreetingTitle(guest), "Welcome to LearnFlow");
  assert.equal(formatGreetingTitle(guest, 9), "Good morning, Learner");
  assert.equal(formatGreetingTitle(guest, 15), "Good afternoon, Learner");
  assert.equal(formatGreetingTitle(guest, 22), "Good evening, Learner");
});

test("formatGreetingTitle handles null, undefined, or malformed identity safely", () => {
  assert.equal(formatGreetingTitle(null), "Welcome to LearnFlow");
  assert.equal(formatGreetingTitle(undefined), "Welcome to LearnFlow");
  assert.equal(formatGreetingTitle({}), "Welcome to LearnFlow");
});

// ---------------------------------------------------------------------------
// 2. getGreetingSubtitle Tests
// ---------------------------------------------------------------------------
test("getGreetingSubtitle provides tailored subtitles for user vs guest", () => {
  const user = { type: "user", id: "u-1", email: "learner@test.com" };
  const guest = { type: "guest", id: "g-1" };

  assert.match(getGreetingSubtitle(user), /Pick up where you left off/);
  assert.match(getGreetingSubtitle(guest), /Explore your documents/);
  assert.match(getGreetingSubtitle(null), /Explore your documents/);
});

// ---------------------------------------------------------------------------
// 3. QUICK_ACTIONS Configuration Tests
// ---------------------------------------------------------------------------
test("QUICK_ACTIONS defines all 4 core workspaces with proper routes and badges", () => {
  assert.equal(QUICK_ACTIONS.length, 4);

  const ids = QUICK_ACTIONS.map((a) => a.id);
  assert.deepEqual(ids, ["study", "revision", "chat", "progress"]);

  const studyAction = QUICK_ACTIONS.find((a) => a.id === "study");
  assert.equal(studyAction.route, ROUTES.STUDY);
  assert.ok(studyAction.description.length > 0);
  assert.ok(studyAction.ariaLabel.includes("Study"));

  const revisionAction = QUICK_ACTIONS.find((a) => a.id === "revision");
  assert.equal(revisionAction.route, ROUTES.REVISION);
  assert.ok(revisionAction.description.includes("Targeted practice"));
  assert.ok(revisionAction.ariaLabel.includes("Revision"));

  const chatAction = QUICK_ACTIONS.find((a) => a.id === "chat");
  assert.equal(chatAction.route, ROUTES.CHAT);
  assert.ok(chatAction.ariaLabel.includes("Chat"));

  const progressAction = QUICK_ACTIONS.find((a) => a.id === "progress");
  assert.equal(progressAction.route, ROUTES.PROGRESS);
  assert.ok(progressAction.ariaLabel.includes("Progress"));
});

// ---------------------------------------------------------------------------
// 4. formatRecentDocumentDate Tests
// ---------------------------------------------------------------------------
test("formatRecentDocumentDate formats dates safely and handles invalid dates", () => {
  assert.equal(formatRecentDocumentDate(null), "--");
  assert.equal(formatRecentDocumentDate(""), "--");
  assert.equal(formatRecentDocumentDate("invalid-date"), "--");

  const formatted = formatRecentDocumentDate("2026-10-15T12:00:00Z");
  assert.match(formatted, /Oct 15, 2026/);
});
