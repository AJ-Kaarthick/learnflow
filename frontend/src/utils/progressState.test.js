import assert from "node:assert/strict";
import { test } from "node:test";
import {
  computeActivityChartData,
  consumePendingRevisionLaunch,
  createLaunchPayloadFromRecommendation,
  createLaunchPayloadFromSchedule,
  createLaunchPayloadFromWeakTopic,
  formatIntervalDays,
  formatMasteryTier,
  formatPercent,
  formatScore,
  formatStruggleIndex,
  formatUrgency,
  formatUtcDate,
  getIdentityScope,
  savePendingRevisionLaunch,
  validateHydratedDocumentsForLaunch,
  validatePendingLaunchPayload,
  VOLUME_METRICS,
} from "./progressState.js";

// ---------------------------------------------------------------------------
// 1. Metric formatting and schema semantics
// ---------------------------------------------------------------------------
test("formatPercent handles 0-1 decimals and preserves null/undefined/NaN as '--'", () => {
  assert.equal(formatPercent(0.85), "85%");
  assert.equal(formatPercent(1.0), "100%");
  assert.equal(formatPercent(0.0), "0%");
  assert.equal(formatPercent(null), "--");
  assert.equal(formatPercent(undefined), "--");
  assert.equal(formatPercent(Number.NaN), "--");
  assert.equal(formatScore(null), "--");
});

test("formatMasteryTier distinguishes mastered, proficient, needs_practice, and unassessed", () => {
  const mastered = formatMasteryTier("mastered", true);
  assert.equal(mastered.tier, "mastered");
  assert.match(mastered.badgeClasses, /emerald/);

  const proficient = formatMasteryTier("proficient", true);
  assert.equal(proficient.tier, "proficient");
  assert.match(proficient.badgeClasses, /blue/);

  const needsPractice = formatMasteryTier("needs_practice", true);
  assert.equal(needsPractice.tier, "needs_practice");
  assert.match(needsPractice.badgeClasses, /amber/);

  const unassessed = formatMasteryTier("mastered", false);
  assert.equal(unassessed.tier, "unassessed");
  assert.equal(unassessed.label, "Unassessed");

  const nullTier = formatMasteryTier(null, true);
  assert.equal(nullTier.tier, "unassessed");
});

test("formatStruggleIndex formats unbounded numbers to 2 decimal places without clamping", () => {
  assert.equal(formatStruggleIndex(0.456), "0.46");
  assert.equal(formatStruggleIndex(1.854), "1.85");
  assert.equal(formatStruggleIndex(3.2), "3.20");
  assert.equal(formatStruggleIndex(0.0), "0.00");
  assert.equal(formatStruggleIndex(null), "--");
  assert.equal(formatStruggleIndex(undefined), "--");
});

test("formatUrgency uses urgency >= 1.0 or isDue as authoritative and displays raw numerical value", () => {
  const due = formatUrgency(1.5, false);
  assert.equal(due.isDue, true);
  assert.equal(due.valueText, "1.50x");
  assert.equal(due.label, "Due for review");
  assert.match(due.badgeClasses, /rose/);

  const upcoming = formatUrgency(0.65, false);
  assert.equal(upcoming.isDue, false);
  assert.equal(upcoming.valueText, "0.65x");
  assert.equal(upcoming.label, "Upcoming");

  const serverDueFlag = formatUrgency(null, true);
  assert.equal(serverDueFlag.isDue, true);
  assert.equal(serverDueFlag.valueText, "--");

  const noUrgency = formatUrgency(null, false);
  assert.equal(noUrgency.isDue, false);
  assert.equal(noUrgency.valueText, "--");
});

test("formatUtcDate formats stable calendar dates in UTC", () => {
  assert.equal(formatUtcDate("2026-10-11"), "Oct 11, 2026");
  assert.equal(formatUtcDate("2026-10-11T14:30:00Z", false), "Oct 11");
  assert.equal(formatUtcDate(null), "--");
  assert.equal(formatIntervalDays(1), "1 day");
  assert.equal(formatIntervalDays(7), "7 days");
});

// ---------------------------------------------------------------------------
// 2. SVG Activity Chart calculations and gap semantics
// ---------------------------------------------------------------------------
test("computeActivityChartData produces separate polyline segments when scores are null (gaps)", () => {
  const timeline = [
    { date: "2026-10-01", questions_attempted: 5, sessions_completed: 1, total_attempts: 7, average_score: 0.8 },
    { date: "2026-10-02", questions_attempted: 0, sessions_completed: 0, total_attempts: 0, average_score: null },
    { date: "2026-10-03", questions_attempted: 4, sessions_completed: 1, total_attempts: 4, average_score: 0.9 },
    { date: "2026-10-04", questions_attempted: 6, sessions_completed: 2, total_attempts: 8, average_score: 0.75 },
  ];

  const chart = computeActivityChartData(timeline, { width: 400, height: 200 });

  assert.equal(chart.isEmpty, false);
  assert.equal(chart.bars.length, 4);
  // Oct 2 had null score: the line MUST split into 2 separate segments rather than bridging across Oct 2!
  assert.equal(chart.scoreSegments.length, 2);
  assert.equal(chart.scorePoints.length, 3);
});

test("computeActivityChartData supports volume metric toggle", () => {
  const timeline = [
    { date: "2026-10-01", questions_attempted: 5, sessions_completed: 2, total_attempts: 10, average_score: 0.8 },
  ];

  const qChart = computeActivityChartData(timeline, { volumeMetric: "questions_attempted" });
  assert.equal(qChart.bars[0].value, 5);

  const sChart = computeActivityChartData(timeline, { volumeMetric: "sessions_completed" });
  assert.equal(sChart.bars[0].value, 2);

  const tChart = computeActivityChartData(timeline, { volumeMetric: "total_attempts" });
  assert.equal(tChart.bars[0].value, 10);
});

test("computeActivityChartData handles edge cases: empty timeline, all zero volume, all null scores", () => {
  const empty = computeActivityChartData([]);
  assert.equal(empty.isEmpty, true);
  assert.equal(empty.bars.length, 0);

  const allZero = [
    { date: "2026-10-01", questions_attempted: 0, sessions_completed: 0, total_attempts: 0, average_score: null },
  ];
  const zeroChart = computeActivityChartData(allZero);
  assert.equal(zeroChart.isEmpty, false);
  assert.equal(zeroChart.maxVolume, 5);
  assert.equal(zeroChart.bars[0].height, 0);
  assert.equal(zeroChart.scoreSegments.length, 0);
  assert.equal(zeroChart.scorePoints.length, 0);
});

// ---------------------------------------------------------------------------
// 3. Identity scoping and safe Revision launch handoff
// ---------------------------------------------------------------------------
test("getIdentityScope distinguishes guest and user IDs and fails safely on missing identity", () => {
  assert.equal(getIdentityScope({ type: "guest", id: "g-123" }), "guest:g-123");
  assert.equal(getIdentityScope({ type: "user", id: "u-456", email: "a@b.com" }), "user:u-456");
  assert.equal(getIdentityScope(null), null);
  assert.equal(getIdentityScope({}), null);
  assert.equal(getIdentityScope({ type: "guest" }), null);
});

test("savePendingRevisionLaunch and consumePendingRevisionLaunch enforce one-shot and identity match", () => {
  const guestIdentity = { type: "guest", id: "g-1" };
  const userIdentity = { type: "user", id: "u-1" };

  const payload = {
    document_ids: ["doc-1"],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: "Mitosis",
  };

  // Save under guest
  const saved = savePendingRevisionLaunch(payload, guestIdentity);
  assert.equal(saved, true);

  // Attempt consume under unresolved identity returns null without clearing prematurely
  const unresolved = consumePendingRevisionLaunch(null);
  assert.equal(unresolved, null);

  // Consume under mismatched user returns null and clears
  const mismatched = consumePendingRevisionLaunch(userIdentity);
  assert.equal(mismatched, null);

  // Resave under guest
  savePendingRevisionLaunch(payload, guestIdentity);

  // Consume under matching guest succeeds
  const consumed = consumePendingRevisionLaunch(guestIdentity);
  assert.deepEqual(consumed, payload);

  // Subsequent consume is empty (one-shot)
  const subsequent = consumePendingRevisionLaunch(guestIdentity);
  assert.equal(subsequent, null);
});

test("validatePendingLaunchPayload sanitizes and clamps bounds", () => {
  const valid = validatePendingLaunchPayload({
    document_ids: ["doc-1", "doc-2"],
    mode: "quiz",
    difficulty: "advanced",
    question_count: 15,
    question_type: "open_ended",
    topic_focus: "Photosynthesis",
  });
  assert.equal(valid.mode, "quiz");
  assert.equal(valid.difficulty, "advanced");
  assert.equal(valid.question_count, 15);
  assert.equal(valid.question_type, "open_ended");
  assert.equal(valid.topic_focus, "Photosynthesis");

  const invalid = validatePendingLaunchPayload({ document_ids: [] });
  assert.equal(invalid, null);

  const fallback = validatePendingLaunchPayload({
    document_ids: ["doc-1"],
    mode: "invalid_mode",
    difficulty: "invalid_diff",
    question_count: 999,
  });
  assert.equal(fallback.mode, "practice");
  assert.equal(fallback.difficulty, "intermediate");
  assert.equal(fallback.question_count, 5);
});

test("createLaunchPayloadFromRecommendation uses authoritative action_payload", () => {
  const rec = {
    id: "rec-1",
    action_payload: {
      document_ids: ["doc-1", "doc-2"],
      mode: "quiz",
      difficulty: "advanced",
      question_count: 10,
      question_type: "mixed",
      topic_focus: "Enzymes",
    },
  };
  const payload = createLaunchPayloadFromRecommendation(rec);
  assert.equal(payload.mode, "quiz");
  assert.equal(payload.difficulty, "advanced");
  assert.equal(payload.question_count, 10);
  assert.equal(payload.topic_focus, "Enzymes");
});

test("createLaunchPayloadFromWeakTopic and createLaunchPayloadFromSchedule build canonical payloads", () => {
  const weakTopic = {
    document_id: "doc-1",
    topic_display: "Cell Cycle",
  };
  const weakPayload = createLaunchPayloadFromWeakTopic(weakTopic);
  assert.deepEqual(weakPayload.document_ids, ["doc-1"]);
  assert.equal(weakPayload.topic_focus, "Cell Cycle");

  const schedule = {
    document_id: "doc-2",
  };
  const srPayload = createLaunchPayloadFromSchedule(schedule);
  assert.deepEqual(srPayload.document_ids, ["doc-2"]);
  assert.equal(srPayload.topic_focus, null);
});

// ---------------------------------------------------------------------------
// 4. Strict all-or-nothing document hydration validation
// ---------------------------------------------------------------------------
test("validateHydratedDocumentsForLaunch strictly checks all document IDs without silent partial drops", () => {
  const hydratedDocs = [
    { id: "doc-1", original_filename: "Doc1.pdf", status: "ready", character_count: 500 },
    { id: "doc-2", original_filename: "Doc2.pdf", status: "processing", character_count: 0 },
    { id: "doc-3", original_filename: "Doc3.pdf", status: "ready", character_count: 1200 },
  ];

  // All valid
  const res1 = validateHydratedDocumentsForLaunch(["doc-1", "doc-3"], hydratedDocs);
  assert.equal(res1.isValid, true);
  assert.equal(res1.validDocs.length, 2);

  // Missing doc-99
  const res2 = validateHydratedDocumentsForLaunch(["doc-1", "doc-99"], hydratedDocs);
  assert.equal(res2.isValid, false);
  assert.deepEqual(res2.missingIds, ["doc-99"]);

  // Unready doc-2
  const res3 = validateHydratedDocumentsForLaunch(["doc-1", "doc-2"], hydratedDocs);
  assert.equal(res3.isValid, false);
  assert.equal(res3.unreadyDocs.length, 1);
  assert.match(res3.reason, /Doc2\.pdf/);
});
