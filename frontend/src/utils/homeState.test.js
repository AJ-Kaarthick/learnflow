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
  getRecommendationActionText,
  getRecommendationBadge,
  getTopRecommendations,
  getTopWeakTopics,
  isRequestCurrent,
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

// ---------------------------------------------------------------------------
// 7. getTopRecommendations Tests
// ---------------------------------------------------------------------------
test("getTopRecommendations returns empty array for null, empty, or invalid input", () => {
  assert.deepEqual(getTopRecommendations(null), []);
  assert.deepEqual(getTopRecommendations(undefined), []);
  assert.deepEqual(getTopRecommendations([]), []);
  assert.deepEqual(getTopRecommendations("string"), []);
});

test("getTopRecommendations slices to max and preserves M5 priority order and fields", () => {
  const mockRecs = [
    {
      id: "rec-1",
      type: "spaced_review",
      priority: 1,
      title: "Review Due: Biology",
      reason: "Optimal retention window reached",
      document_id: "doc-1",
      document_title: "Biology 101",
      is_archived: false,
      is_actionable: true,
      urgency: 1.45,
      due_date: "2026-10-22T00:00:00Z",
      action_payload: { document_ids: ["doc-1"], mode: "practice", difficulty: "intermediate" },
    },
    {
      id: "rec-2",
      type: "weak_topic_practice",
      priority: 2,
      title: "Practice Weak Topic: Photosynthesis",
      reason: "High struggle detected",
      document_id: "doc-1",
      document_title: "Biology 101",
      is_archived: false,
      is_actionable: true,
      topic_focus: "Photosynthesis",
      struggle_index: 2.15,
      action_payload: { document_ids: ["doc-1"], topic_focus: "Photosynthesis" },
    },
    {
      id: "rec-3",
      type: "unrevised_document",
      priority: 3,
      title: "First Revision: Chemistry",
      reason: "Unrevised document",
      document_id: "doc-2",
      document_title: "Chemistry Notes",
      is_archived: false,
      is_actionable: true,
    },
  ];

  const topTwo = getTopRecommendations(mockRecs, 2);
  assert.equal(topTwo.length, 2);

  // Priority 1 preserved
  assert.equal(topTwo[0].id, "rec-1");
  assert.equal(topTwo[0].type, "spaced_review");
  assert.equal(topTwo[0].priority, 1);
  assert.equal(topTwo[0].title, "Review Due: Biology");
  assert.equal(topTwo[0].isActionable, true);
  assert.equal(topTwo[0].urgency, 1.45);

  // Priority 2 preserved
  assert.equal(topTwo[1].id, "rec-2");
  assert.equal(topTwo[1].type, "weak_topic_practice");
  assert.equal(topTwo[1].priority, 2);
  assert.equal(topTwo[1].topicFocus, "Photosynthesis");
  assert.equal(topTwo[1].struggleIndex, 2.15);
});

test("getTopRecommendations safely handles archived and non-actionable recommendations", () => {
  const mockRecs = [
    {
      id: "rec-archived",
      type: "spaced_review",
      title: "Archived Doc",
      document_id: "doc-archived",
      document_title: "Old Doc",
      is_archived: true,
      is_actionable: false,
    },
    {
      id: "rec-missing-id",
      type: "unrevised_document",
      title: "No ID Doc",
      document_id: null,
      is_archived: false,
      is_actionable: true,
    },
  ];

  const top = getTopRecommendations(mockRecs);
  assert.equal(top[0].isArchived, true);
  assert.equal(top[0].isActionable, false);

  assert.equal(top[1].isActionable, false);
});

// ---------------------------------------------------------------------------
// 8. getRecommendationBadge Tests
// ---------------------------------------------------------------------------
test("getRecommendationBadge returns correct labels and styling tokens", () => {
  assert.equal(getRecommendationBadge("spaced_review").label, "Spaced Review");
  assert.match(getRecommendationBadge("spaced_review").badgeClasses, /amber/);

  assert.equal(getRecommendationBadge("weak_topic_practice").label, "Weak Topic");
  assert.match(getRecommendationBadge("weak_topic_practice").badgeClasses, /rose/);

  assert.equal(getRecommendationBadge("unrevised_document").label, "New Document");
  assert.match(getRecommendationBadge("unrevised_document").badgeClasses, /blue/);

  assert.equal(getRecommendationBadge("unknown").label, "Recommendation");
});

// ---------------------------------------------------------------------------
// 9. getRecommendationActionText Tests
// ---------------------------------------------------------------------------
test("getRecommendationActionText returns tailored CTA or disabled status", () => {
  assert.equal(getRecommendationActionText(null), "Not Ready");
  assert.equal(getRecommendationActionText({ isActionable: false, isArchived: true }), "Archived");
  assert.equal(getRecommendationActionText({ isActionable: false, isArchived: false }), "Not Ready");

  assert.equal(
    getRecommendationActionText({ isActionable: true, isArchived: false, type: "spaced_review" }),
    "Review Now"
  );
  assert.equal(
    getRecommendationActionText({ isActionable: true, isArchived: false, type: "weak_topic_practice" }),
    "Practice Topic"
  );
  assert.equal(
    getRecommendationActionText({ isActionable: true, isArchived: false, type: "unrevised_document" }),
    "Start Revision"
  );
});

// ---------------------------------------------------------------------------
// 10. getTopWeakTopics Tests
// ---------------------------------------------------------------------------
test("getTopWeakTopics returns empty array for null or empty input", () => {
  assert.deepEqual(getTopWeakTopics(null), []);
  assert.deepEqual(getTopWeakTopics(undefined), []);
  assert.deepEqual(getTopWeakTopics([]), []);
});

test("getTopWeakTopics slices to max and sanitizes weak topic properties", () => {
  const mockWeak = [
    {
      topic_key: "mitosis",
      topic_display: "Mitosis & Cell Division",
      document_id: "doc-1",
      document_title: "Cell Biology",
      is_archived: false,
      is_actionable: true,
      struggle_index: 3.4,
      mastery_score: 0.25,
      total_attempts: 8,
      distinct_attempted_questions: 4,
    },
    {
      topic_key: "glycolysis",
      topic_display: "Glycolysis Pathway",
      document_id: "doc-1",
      document_title: "Cell Biology",
      is_archived: false,
      is_actionable: true,
      struggle_index: 2.1,
      mastery_score: 0.4,
      total_attempts: 5,
      distinct_attempted_questions: 3,
    },
    {
      topic_key: "krebs",
      topic_display: "Krebs Cycle",
      document_id: "doc-1",
      document_title: "Cell Biology",
      is_archived: false,
      is_actionable: true,
    },
  ];

  const top = getTopWeakTopics(mockWeak, 2);
  assert.equal(top.length, 2);

  assert.equal(top[0].topicDisplay, "Mitosis & Cell Division");
  assert.equal(top[0].documentTitle, "Cell Biology");
  assert.equal(top[0].struggleIndex, 3.4);
  assert.equal(top[0].isActionable, true);

  assert.equal(top[1].topicDisplay, "Glycolysis Pathway");
  assert.equal(top[1].struggleIndex, 2.1);
});

test("getTopWeakTopics returns empty array when no actionable weak topics exist (truthful empty state)", () => {
  const onlyArchived = [
    {
      topic_key: "archived_topic_1",
      topic_display: "Archived Topic 1",
      document_id: "doc-archived-1",
      document_title: "Old Doc",
      is_archived: true,
      is_actionable: false,
      struggle_index: 3.8,
    },
    {
      topic_key: "archived_topic_2",
      topic_display: "Archived Topic 2",
      document_id: null,
      document_title: "",
      is_archived: false,
      is_actionable: false,
      struggle_index: 2.5,
    },
  ];

  // Must return empty array so Home renders truthful empty state
  assert.deepEqual(getTopWeakTopics(onlyArchived), []);
});

test("getTopWeakTopics handles archived document fallback when retained alongside actionable topic", () => {
  const mixed = [
    {
      topic_key: "active_topic",
      topic_display: "Active Topic",
      document_id: "doc-active",
      document_title: "Active Document",
      is_archived: false,
      is_actionable: true,
      struggle_index: 2.0,
    },
    {
      topic_key: "archived_topic",
      topic_display: "Archived Topic",
      document_id: "doc-deleted",
      document_title: "",
      is_archived: true,
      is_actionable: false,
      struggle_index: 3.5,
    },
  ];

  const top = getTopWeakTopics(mixed, 2);
  assert.equal(top.length, 2);
  assert.equal(top[0].isActionable, true);
  assert.equal(top[0].topicDisplay, "Active Topic");
  assert.equal(top[1].documentTitle, "Archived Document");
  assert.equal(top[1].isArchived, true);
  assert.equal(top[1].isActionable, false);
});

test("getTopWeakTopics prevents archived topics from crowding out active practice-ready topics in mixed lists", () => {
  // Backend returns deterministically sorted by highest struggle index first
  const mixed = [
    {
      topic_key: "archived_high_struggle",
      topic_display: "Archived High Struggle",
      document_id: "doc-archived",
      document_title: "Old Biology",
      is_archived: true,
      is_actionable: false,
      struggle_index: 4.8,
      mastery_score: 0.1,
    },
    {
      topic_key: "actionable_topic_1",
      topic_display: "Actionable Concept 1",
      document_id: "doc-1",
      document_title: "Active Chemistry",
      is_archived: false,
      is_actionable: true,
      struggle_index: 3.5,
      mastery_score: 0.2,
    },
    {
      topic_key: "actionable_topic_2",
      topic_display: "Actionable Concept 2",
      document_id: "doc-2",
      document_title: "Active Physics",
      is_archived: false,
      is_actionable: true,
      struggle_index: 2.8,
      mastery_score: 0.35,
    },
  ];

  const top = getTopWeakTopics(mixed, 2);
  assert.equal(top.length, 2);

  // Both slots must be practice-ready actionable topics; archived item must NOT crowd out actionable_topic_2
  assert.equal(top[0].topicKey, "actionable_topic_1");
  assert.equal(top[0].isActionable, true);
  assert.equal(top[1].topicKey, "actionable_topic_2");
  assert.equal(top[1].isActionable, true);
});

test("getTopWeakTopics handles mixed lists containing actionable, archived, non-ready, and malformed records", () => {
  const mixedList = [
    null,
    undefined,
    "invalid string record",
    42,
    {
      // Non-ready (missing document_id)
      topic_key: "unready_no_doc",
      topic_display: "Unready Topic",
      document_id: null,
      document_title: "Missing Document",
      is_archived: false,
      is_actionable: false,
      struggle_index: 5.0,
    },
    {
      // Archived item
      topic_key: "archived_item",
      topic_display: "Archived Topic",
      document_id: "doc-deleted",
      document_title: "Deleted Doc",
      is_archived: true,
      is_actionable: false,
      struggle_index: 4.2,
    },
    {
      // Actionable item 1
      topic_key: "actionable_item_1",
      topic_display: "Actionable Item 1",
      document_id: "doc-10",
      document_title: "Calculus I",
      is_archived: false,
      is_actionable: true,
      struggle_index: 3.1,
      mastery_score: 0.25,
      total_attempts: 6,
    },
    {
      // Malformed object without topic or document
      not_a_valid_record: true,
    },
    {
      // Actionable item 2
      topic_key: "actionable_item_2",
      topic_display: "Actionable Item 2",
      document_id: "doc-11",
      document_title: "Linear Algebra",
      is_archived: false,
      is_actionable: true,
      struggle_index: 2.2,
      mastery_score: 0.45,
      total_attempts: 4,
    },
  ];

  const top = getTopWeakTopics(mixedList, 2);
  assert.equal(top.length, 2);

  // Safely selected the two actionable topics in their backend relative priority order
  assert.equal(top[0].topicKey, "actionable_item_1");
  assert.equal(top[0].documentId, "doc-10");
  assert.equal(top[0].isActionable, true);

  assert.equal(top[1].topicKey, "actionable_item_2");
  assert.equal(top[1].documentId, "doc-11");
  assert.equal(top[1].isActionable, true);
});

// ---------------------------------------------------------------------------
// 11. isRequestCurrent Isolation Tests
// ---------------------------------------------------------------------------
test("isRequestCurrent validates matching generation and identity scope", () => {
  assert.equal(isRequestCurrent(1, "user:u1", 1, "user:u1"), true);
  assert.equal(isRequestCurrent(2, "guest:g1", 2, "guest:g1"), true);

  // Stale generation (e.g. newer retry launched)
  assert.equal(isRequestCurrent(1, "user:u1", 2, "user:u1"), false);

  // Mismatched scope (e.g. user logged in or switched account)
  assert.equal(isRequestCurrent(1, "guest:g1", 1, "user:u1"), false);
  assert.equal(isRequestCurrent(1, "user:u1", 1, "user:u2"), false);

  // Null, undefined, or missing scope fails safely
  assert.equal(isRequestCurrent(1, null, 1, "user:u1"), false);
  assert.equal(isRequestCurrent(1, "user:u1", 1, null), false);
  assert.equal(isRequestCurrent(1, null, 1, null), false);
  assert.equal(isRequestCurrent(1, undefined, 1, undefined), false);
});

// ---------------------------------------------------------------------------
// 12. Learning Pulse & Activity Feed Helpers Re-Export Tests (Phase 4)
// ---------------------------------------------------------------------------
test("homeState re-exports all Learning Pulse and Activity Feed helpers", async () => {
  const homeStateModule = await import("./homeState.js");
  assert.equal(typeof homeStateModule.calculateOverdueReviewsCount, "function");
  assert.equal(typeof homeStateModule.extractLearningPulseKPIs, "function");
  assert.equal(typeof homeStateModule.formatActivityDate, "function");
  assert.equal(typeof homeStateModule.formatKPIAccuracy, "function");
  assert.equal(typeof homeStateModule.formatKPICount, "function");
  assert.equal(typeof homeStateModule.mergeRecentLearningActivity, "function");
});
