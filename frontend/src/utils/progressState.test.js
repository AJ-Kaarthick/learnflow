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
test("formatPercent and formatScore safely handle decimals and reject non-finite/null values as '--'", () => {
  assert.equal(formatPercent(0.85), "85%");
  assert.equal(formatPercent(1.0), "100%");
  assert.equal(formatPercent(0.0), "0%");
  assert.equal(formatPercent(null), "--");
  assert.equal(formatPercent(undefined), "--");
  assert.equal(formatPercent(Number.NaN), "--");
  assert.equal(formatPercent(Infinity), "--");
  assert.equal(formatPercent(-Infinity), "--");
  assert.equal(formatPercent(""), "--");
  assert.equal(formatPercent("invalid"), "--");

  assert.equal(formatScore(0.85), "85%");
  assert.equal(formatScore(1.0), "100%");
  assert.equal(formatScore(0.0), "0%");
  assert.equal(formatScore(null), "--");
  assert.equal(formatScore(undefined), "--");
  assert.equal(formatScore(Number.NaN), "--");
  assert.equal(formatScore(Infinity), "--");
  assert.equal(formatScore(-Infinity), "--");
  assert.equal(formatScore("invalid"), "--");
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

test("formatStruggleIndex formats unbounded numbers to 2 decimal places without clamping and safely rejects non-finite values", () => {
  assert.equal(formatStruggleIndex(0.456), "0.46");
  assert.equal(formatStruggleIndex(1.854), "1.85");
  assert.equal(formatStruggleIndex(3.2), "3.20");
  assert.equal(formatStruggleIndex(0.0), "0.00");
  assert.equal(formatStruggleIndex(null), "--");
  assert.equal(formatStruggleIndex(undefined), "--");
  assert.equal(formatStruggleIndex(Number.NaN), "--");
  assert.equal(formatStruggleIndex(Infinity), "--");
  assert.equal(formatStruggleIndex(-Infinity), "--");
  assert.equal(formatStruggleIndex("not-a-number"), "--");
});

test("formatUrgency uses urgency >= 1.0 or isDue as authoritative, displays raw numerical value, and rejects non-finite values", () => {
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

  const nanUrgency = formatUrgency(Number.NaN, false);
  assert.equal(nanUrgency.isDue, false);
  assert.equal(nanUrgency.valueText, "--");

  const infUrgency = formatUrgency(Infinity, false);
  assert.equal(infUrgency.isDue, false);
  assert.equal(infUrgency.valueText, "--");

  const negInfUrgency = formatUrgency(-Infinity, false);
  assert.equal(negInfUrgency.isDue, false);
  assert.equal(negInfUrgency.valueText, "--");

  const strUrgency = formatUrgency("not-numeric", false);
  assert.equal(strUrgency.isDue, false);
  assert.equal(strUrgency.valueText, "--");
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

test("computeActivityChartData anchors all score points strictly inside the plot area", () => {
  const width = 640;
  const height = 240;
  const padding = { top: 24, right: 40, bottom: 36, left: 40 };

  const timeline = [
    { date: "2026-10-01", questions_attempted: 1, average_score: 0.0 }, // minimum score bound
    { date: "2026-10-02", questions_attempted: 2, average_score: 0.5 },
    { date: "2026-10-03", questions_attempted: 3, average_score: 1.0 }, // maximum score bound
    { date: "2026-10-04", questions_attempted: 4, average_score: 1.2 }, // over 1.0 clamped
    { date: "2026-10-05", questions_attempted: 5, average_score: 0.2 },
    { date: "2026-10-06", questions_attempted: 6, average_score: 0.85 },
    { date: "2026-10-07", questions_attempted: 7, average_score: 0.95 },
  ];

  const chart = computeActivityChartData(timeline, { width, height, padding });
  assert.equal(chart.scorePoints.length, 7);

  const minX = padding.left;
  const maxX = width - padding.right;
  const minY = padding.top;
  const maxY = height - padding.bottom;

  for (const pt of chart.scorePoints) {
    assert.ok(pt.x >= minX && pt.x <= maxX, `pt.x (${pt.x}) must be within [${minX}, ${maxX}]`);
    assert.ok(pt.y >= minY && pt.y <= maxY, `pt.y (${pt.y}) must be within [${minY}, ${maxY}]`);
  }
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

test("validatePendingLaunchPayload strictly validates valid payloads and rejects malformed inputs", () => {
  const valid = validatePendingLaunchPayload({
    document_ids: ["doc-1", "doc-2"],
    mode: "quiz",
    difficulty: "advanced",
    question_count: 15,
    question_type: "open_ended",
    topic_focus: "Photosynthesis",
  });
  assert.deepEqual(valid, {
    document_ids: ["doc-1", "doc-2"],
    mode: "quiz",
    difficulty: "advanced",
    question_count: 15,
    question_type: "open_ended",
    topic_focus: "Photosynthesis",
  });

  // Null or non-object payloads
  assert.equal(validatePendingLaunchPayload(null), null);
  assert.equal(validatePendingLaunchPayload("not-an-object"), null);

  // Empty document_ids array
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: [],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );

  // Any invalid document ID in array rejects the whole payload without filtering
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1", ""],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1", null],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1", "   "],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );

  // More than 10 documents
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: Array.from({ length: 11 }, (_, i) => `doc-${i}`),
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );

  // Invalid mode (rejected, not defaulted)
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "invalid_mode",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );

  // Invalid difficulty (rejected, not defaulted)
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "invalid_diff",
      question_count: 5,
      question_type: "multiple_choice",
    }),
    null
  );

  // Invalid question_type (rejected, not defaulted)
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "invalid_type",
    }),
    null
  );

  // Question count bounds and types (1-20 integer)
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 0,
      question_type: "multiple_choice",
    }),
    null
  );
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 21,
      question_type: "multiple_choice",
    }),
    null
  );
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5.5,
      question_type: "multiple_choice",
    }),
    null
  );
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: "abc",
      question_type: "multiple_choice",
    }),
    null
  );

  // topic_focus > 100 chars (rejected, not silently truncated)
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
      topic_focus: "A".repeat(101),
    }),
    null
  );

  // topic_focus non-string
  assert.equal(
    validatePendingLaunchPayload({
      document_ids: ["doc-1"],
      mode: "practice",
      difficulty: "intermediate",
      question_count: 5,
      question_type: "multiple_choice",
      topic_focus: 123,
    }),
    null
  );

  // Canonical recommendation payload with topic_focus: null
  const canonical = validatePendingLaunchPayload({
    document_ids: ["doc-1"],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: null,
  });
  assert.deepEqual(canonical, {
    document_ids: ["doc-1"],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: null,
  });
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
