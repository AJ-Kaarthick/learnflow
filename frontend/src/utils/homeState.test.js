import assert from "node:assert/strict";
import { test } from "node:test";
import { ROUTES } from "../router/useHashRoute.js";
import {
  QUICK_ACTIONS,
  extractInProgressSession,
  formatGreetingTitle,
  formatInProgressSessionProgress,
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

// ---------------------------------------------------------------------------
// 5. extractInProgressSession Tests
// ---------------------------------------------------------------------------
test("extractInProgressSession returns null for empty, null, or non-array inputs", () => {
  assert.equal(extractInProgressSession(null), null);
  assert.equal(extractInProgressSession(undefined), null);
  assert.equal(extractInProgressSession([]), null);
  assert.equal(extractInProgressSession({}), null);
});

test("extractInProgressSession ignores completed, abandoned, or missing ID sessions", () => {
  const sessions = [
    { id: "s-comp", status: "completed", title: "Done Session" },
    { id: "s-aband", status: "abandoned", title: "Abandoned Session" },
    { id: "", status: "in_progress", title: "Invalid ID" },
    { id: null, status: "in_progress", title: "Null ID" },
  ];
  assert.equal(extractInProgressSession(sessions), null);
});

test("extractInProgressSession extracts first in_progress session with safe fallbacks", () => {
  const sessions = [
    { id: "s-done", status: "completed", title: "Old Completed Session" },
    {
      id: "s-active-1",
      status: "in_progress",
      title: "  Biology Unit 2  ",
      config: { difficulty: "advanced", mode: "quiz" },
      total_questions: 10,
    },
    {
      id: "s-active-2",
      status: "in_progress",
      title: "Second in progress",
    },
  ];

  const extracted = extractInProgressSession(sessions);
  assert.ok(extracted);
  assert.equal(extracted.id, "s-active-1");
  assert.equal(extracted.title, "Biology Unit 2");
  assert.equal(extracted.difficulty, "advanced");
  assert.equal(extracted.mode, "quiz");
  assert.equal(extracted.totalQuestions, 10);
  assert.equal(extracted.answeredQuestions, null);
  assert.equal(extracted.progressPercentage, null);
});

test("extractInProgressSession uses 'Untitled Revision Session' fallback when title is missing", () => {
  const sessions = [
    {
      id: "s-no-title",
      status: "in_progress",
      title: "   ",
      total_questions: 5,
    },
  ];

  const extracted = extractInProgressSession(sessions);
  assert.equal(extracted.title, "Untitled Revision Session");
});

test("extractInProgressSession derives answered count and progress percentage from questions", () => {
  const sessionDetail = {
    id: "s-detail",
    status: "in_progress",
    title: "Detailed Session",
    total_questions: 4,
    questions: [
      { id: "q1", attempts: [{ score: 1.0 }] },
      { id: "q2", attempts: [{ score: 0.5 }, { score: 1.0 }] },
      { id: "q3", attempts: [] },
      { id: "q4", attempts: null },
    ],
  };

  const extracted = extractInProgressSession([sessionDetail]);
  assert.equal(extracted.totalQuestions, 4);
  assert.equal(extracted.answeredQuestions, 2);
  assert.equal(extracted.progressPercentage, 50);
});

test("extractInProgressSession supports answered_questions integer property", () => {
  const session = {
    id: "s-prop",
    status: "in_progress",
    title: "Property Session",
    total_questions: 10,
    answered_questions: 3,
  };

  const extracted = extractInProgressSession([session]);
  assert.equal(extracted.totalQuestions, 10);
  assert.equal(extracted.answeredQuestions, 3);
  assert.equal(extracted.progressPercentage, 30);
});

// ---------------------------------------------------------------------------
// 6. formatInProgressSessionProgress Tests
// ---------------------------------------------------------------------------
test("formatInProgressSessionProgress formats progress variations accurately", () => {
  assert.equal(formatInProgressSessionProgress(null), "Revision session in progress");

  assert.equal(
    formatInProgressSessionProgress({ answeredQuestions: 3, totalQuestions: 5 }),
    "3 of 5 questions answered"
  );

  assert.equal(
    formatInProgressSessionProgress({ answeredQuestions: null, totalQuestions: 10 }),
    "10 questions"
  );

  assert.equal(
    formatInProgressSessionProgress({ answeredQuestions: null, totalQuestions: null }),
    "Revision session in progress"
  );
});
