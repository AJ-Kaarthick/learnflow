import assert from "node:assert/strict";
import { test } from "node:test";
import {
  calculateOverdueReviewsCount,
  extractLearningPulseKPIs,
  formatActivityDate,
  formatKPIAccuracy,
  formatKPICount,
  mergeRecentLearningActivity,
} from "./homePulse.js";

test("1. calculateOverdueReviewsCount filters strictly by due, actionable, unarchived, with history", () => {
  assert.equal(calculateOverdueReviewsCount(null), null);
  assert.equal(calculateOverdueReviewsCount(undefined), null);
  assert.equal(calculateOverdueReviewsCount("not-an-array"), null);
  assert.equal(calculateOverdueReviewsCount([]), 0);

  const schedules = [
    // Eligible: due, actionable, not archived, has history
    { id: "s1", is_due: true, is_actionable: true, is_archived: false, has_history: true },
    // Eligible: has_history omitted (defaults to true)
    { id: "s2", is_due: true, is_actionable: true, is_archived: false },
    // Ineligible: not due
    { id: "s3", is_due: false, is_actionable: true, is_archived: false, has_history: true },
    // Ineligible: not actionable
    { id: "s4", is_due: true, is_actionable: false, is_archived: false, has_history: true },
    // Ineligible: archived
    { id: "s5", is_due: true, is_actionable: true, is_archived: true, has_history: true },
    // Ineligible: has_history is false
    { id: "s6", is_due: true, is_actionable: true, is_archived: false, has_history: false },
  ];

  assert.equal(calculateOverdueReviewsCount(schedules), 2);
});

test("2. formatKPICount converts valid numbers and safely rejects invalid values", () => {
  assert.equal(formatKPICount(0), "0");
  assert.equal(formatKPICount(15), "15");
  assert.equal(formatKPICount("42"), "42");
  assert.equal(formatKPICount(null), "--");
  assert.equal(formatKPICount(undefined), "--");
  assert.equal(formatKPICount(Number.NaN), "--");
  assert.equal(formatKPICount(""), "--");
  assert.equal(formatKPICount(-5), "--");
});

test("3. formatKPIAccuracy formats percentage or '--' without fabricating zero", () => {
  assert.equal(formatKPIAccuracy(0.85, 20), "85%");
  assert.equal(formatKPIAccuracy(1.0, 5), "100%");
  assert.equal(formatKPIAccuracy(0.0, 5), "0%");

  // Unassessed / 0 total attempts must be '--'
  assert.equal(formatKPIAccuracy(0.0, 0), "--");
  assert.equal(formatKPIAccuracy(0.85, 0), "--");
  assert.equal(formatKPIAccuracy(null, 10), "--");
  assert.equal(formatKPIAccuracy(undefined, 10), "--");
  assert.equal(formatKPIAccuracy(Number.NaN, 10), "--");
});

test("4. extractLearningPulseKPIs produces all 4 canonical KPIs with accurate schemas", () => {
  const summary = {
    total_attempted_questions: 28,
    total_completed_sessions: 7,
    total_attempts: 35,
    overall_attempt_accuracy: 0.857,
  };

  const schedules = [
    { id: "s1", is_due: true, is_actionable: true, is_archived: false },
    { id: "s2", is_due: false, is_actionable: true, is_archived: false },
  ];

  const kpis = extractLearningPulseKPIs(summary, schedules);

  assert.equal(kpis.questionsAttempted.value, "28");
  assert.equal(kpis.questionsAttempted.label, "Questions Attempted");

  assert.equal(kpis.overdueReviews.value, "1");
  assert.equal(kpis.overdueReviews.label, "Overdue Reviews");

  assert.equal(kpis.attemptAccuracy.value, "86%");
  assert.equal(kpis.attemptAccuracy.label, "Attempt Accuracy");

  assert.equal(kpis.completedSessions.value, "7");
  assert.equal(kpis.completedSessions.label, "Completed Sessions");
});

test("5. extractLearningPulseKPIs handles null/empty data gracefully", () => {
  const kpis = extractLearningPulseKPIs(null, null);

  assert.equal(kpis.questionsAttempted.value, "--");
  assert.equal(kpis.overdueReviews.value, "--");
  assert.equal(kpis.attemptAccuracy.value, "--");
  assert.equal(kpis.completedSessions.value, "--");

  // When schedules is empty array, overdueReviews should show genuine 0
  const kpisWithEmptySchedules = extractLearningPulseKPIs(null, []);
  assert.equal(kpisWithEmptySchedules.overdueReviews.value, "0");
});

test("6. formatActivityDate formats date correctly and handles invalid inputs", () => {
  assert.equal(formatActivityDate(null), "--");
  assert.equal(formatActivityDate("invalid-date"), "--");

  const formatted = formatActivityDate("2026-10-21T14:30:00Z");
  assert.match(formatted, /Oct 21, 2026/);
});

test("7. mergeRecentLearningActivity merges sessions and documents chronologically", () => {
  const sessions = [
    {
      id: "sess-1",
      title: "Cell Biology Quiz",
      status: "completed",
      mode: "quiz",
      score: 0.9,
      completed_at: "2026-10-22T10:00:00Z",
    },
    {
      id: "sess-2",
      title: "Unfinished Revision",
      status: "in_progress", // Must be ignored
      completed_at: null,
    },
  ];

  const documents = [
    {
      id: "doc-1",
      original_filename: "Chemistry Notes.pdf",
      last_opened_at: "2026-10-22T12:00:00Z", // Newer than sess-1
      created_at: "2026-10-20T08:00:00Z",
    },
    {
      id: "doc-2",
      original_filename: "History Syllabus.pdf",
      last_opened_at: null, // Never opened
      created_at: "2026-10-22T08:00:00Z", // Older than sess-1
    },
  ];

  const activity = mergeRecentLearningActivity({ documents, sessions, limit: 5 });

  assert.equal(activity.length, 3);

  // 1. Chemistry Notes opened at 12:00 -> "Studied"
  assert.equal(activity[0].id, "doc-1");
  assert.equal(activity[0].title, "Chemistry Notes.pdf");
  assert.equal(activity[0].badgeLabel, "Studied");
  assert.equal(activity[0].type, "document");

  // 2. Cell Biology Quiz completed at 10:00 -> "Quiz", "90%"
  assert.equal(activity[1].id, "sess-1");
  assert.equal(activity[1].title, "Cell Biology Quiz");
  assert.equal(activity[1].badgeLabel, "Quiz");
  assert.equal(activity[1].score, "90%");
  assert.equal(activity[1].type, "revision");

  // 3. History Syllabus uploaded at 08:00 -> "Uploaded" (never "Studied")
  assert.equal(activity[2].id, "doc-2");
  assert.equal(activity[2].title, "History Syllabus.pdf");
  assert.equal(activity[2].badgeLabel, "Uploaded");
  assert.equal(activity[2].type, "document");
});

test("8. mergeRecentLearningActivity respects limit and handles empty arrays", () => {
  assert.deepEqual(mergeRecentLearningActivity(), []);
  assert.deepEqual(mergeRecentLearningActivity({ documents: [], sessions: [] }), []);

  const sessions = [
    { id: "s1", status: "completed", completed_at: "2026-10-22T10:00:00Z", score: 0.8 },
    { id: "s2", status: "completed", completed_at: "2026-10-22T09:00:00Z", score: 0.7 },
  ];
  const documents = [
    { id: "d1", original_filename: "A.pdf", last_opened_at: "2026-10-22T11:00:00Z" },
    { id: "d2", original_filename: "B.pdf", last_opened_at: "2026-10-22T08:00:00Z" },
  ];

  const limited = mergeRecentLearningActivity({ documents, sessions, limit: 2 });
  assert.equal(limited.length, 2);
  assert.equal(limited[0].id, "d1");
  assert.equal(limited[1].id, "s1");
});
