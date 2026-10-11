/**
 * Pure state, formatting, SVG chart math, launcher handoff, and identity-scoping
 * utilities for LearnFlow Progress Workspace (V3 Milestone 5 Phase 4).
 *
 * All functions are deterministic and independent of React rendering.
 */

export const VOLUME_METRICS = [
  { id: "questions_attempted", label: "Questions Attempted", description: "Distinct questions practiced" },
  { id: "sessions_completed", label: "Completed Sessions", description: "Finished revision sessions" },
  { id: "total_attempts", label: "Total Attempts", description: "All attempts including retries" },
];

function isFiniteNumber(val) {
  if (val === null || val === undefined || val === "") return false;
  const num = typeof val === "number" ? val : Number(val);
  return typeof num === "number" && Number.isFinite(num);
}

/**
 * Formats a fractional number (0.0 to 1.0) into a clean percentage string (e.g. "85%").
 * Returns "--" for null, undefined, NaN, or non-finite values without fabricating zero.
 */
export function formatPercent(val) {
  if (!isFiniteNumber(val)) {
    return "--";
  }
  const num = Number(val);
  return `${Math.round(num * 100)}%`;
}

/**
 * Formats a numeric score into a percentage or fallback.
 */
export function formatScore(val) {
  return formatPercent(val);
}

/**
 * Formats a recency-decayed mastery tier into human-readable label and Tailwind badge classes.
 */
export function formatMasteryTier(tier, isAssessed = true) {
  if (!isAssessed || !tier || tier === "unassessed") {
    return {
      label: "Unassessed",
      tier: "unassessed",
      badgeClasses: "bg-slate-100 text-slate-700 border-slate-200",
    };
  }

  switch (tier.toLowerCase()) {
    case "mastered":
      return {
        label: "Mastered",
        tier: "mastered",
        badgeClasses: "bg-emerald-50 text-emerald-700 border-emerald-200",
      };
    case "proficient":
      return {
        label: "Proficient",
        tier: "proficient",
        badgeClasses: "bg-blue-50 text-blue-700 border-blue-200",
      };
    case "needs_practice":
      return {
        label: "Needs Practice",
        tier: "needs_practice",
        badgeClasses: "bg-amber-50 text-amber-700 border-amber-200",
      };
    default:
      return {
        label: tier,
        tier,
        badgeClasses: "bg-slate-100 text-slate-700 border-slate-200",
      };
  }
}

/**
 * Formats an unbounded struggle index to 2 decimal places.
 * Never clamps the value to 0-1, and safely rejects non-finite values.
 */
export function formatStruggleIndex(index) {
  if (!isFiniteNumber(index)) {
    return "--";
  }
  return Number(index).toFixed(2);
}

/**
 * Formats an urgency metric and derives review status.
 * Authoritative review status uses urgency >= 1.0 or server-provided isDue flag.
 * Safely rejects non-finite urgency values without displaying Infinityx or NaN.
 */
export function formatUrgency(urgency, isDue = false) {
  const hasUrgency = isFiniteNumber(urgency);
  const numericUrgency = hasUrgency ? Number(urgency) : null;
  const isDueActive = Boolean(isDue || (numericUrgency !== null && numericUrgency >= 1.0));

  return {
    valueText: numericUrgency !== null ? `${numericUrgency.toFixed(2)}x` : "--",
    numericValue: numericUrgency,
    isDue: isDueActive,
    label: isDueActive ? "Due for review" : "Upcoming",
    badgeClasses: isDueActive
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : "bg-slate-50 text-slate-600 border-slate-200",
  };
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * Formats a YYYY-MM-DD or ISO string into a stable calendar date in UTC,
 * avoiding local timezone shifts across midnight.
 */
export function formatUtcDate(dateStr, includeYear = true) {
  if (!dateStr || typeof dateStr !== "string") {
    return "--";
  }
  const clean = dateStr.slice(0, 10);
  const parts = clean.split("-");
  if (parts.length !== 3) {
    return dateStr;
  }
  const year = parts[0];
  const monthIdx = Number.parseInt(parts[1], 10) - 1;
  const day = Number.parseInt(parts[2], 10);

  if (monthIdx < 0 || monthIdx > 11 || Number.isNaN(day)) {
    return dateStr;
  }

  const monthName = MONTH_NAMES[monthIdx] || parts[1];
  return includeYear ? `${monthName} ${day}, ${year}` : `${monthName} ${day}`;
}

/**
 * Formats an interval in days.
 */
export function formatIntervalDays(days) {
  if (days === null || days === undefined) return "--";
  return days === 1 ? "1 day" : `${days} days`;
}

/**
 * Computes SVG coordinates for dual-axis activity timeline (volume bars + average score trend).
 *
 * Explicit rules:
 * - Null average-score days create VISIBLE GAPS in the score trend line by producing
 *   separate contiguous line segments rather than connecting across missing days.
 * - Volume bars can toggle between questions_attempted, sessions_completed, or total_attempts.
 * - All math handles empty data, all-zero volume, and all-null scores gracefully.
 *
 * @param {Array<Object>} timeline - List of DailyActivityItem
 * @param {Object} [options]
 * @returns {Object} Chart geometry data
 */
export function computeActivityChartData(
  timeline = [],
  {
    width = 640,
    height = 240,
    padding = { top: 24, right: 40, bottom: 36, left: 40 },
    volumeMetric = "questions_attempted",
  } = {}
) {
  if (!Array.isArray(timeline) || timeline.length === 0) {
    return {
      isEmpty: true,
      bars: [],
      scoreSegments: [],
      scorePoints: [],
      xLabels: [],
      maxVolume: 0,
      width,
      height,
    };
  }

  const plotWidth = Math.max(10, width - padding.left - padding.right);
  const plotHeight = Math.max(10, height - padding.top - padding.bottom);

  // Extract raw volume values based on selected metric
  const volumes = timeline.map((d) => {
    const raw = d[volumeMetric];
    return isFiniteNumber(raw) && Number(raw) >= 0 ? Number(raw) : 0;
  });

  const rawMaxVolume = Math.max(0, ...volumes);
  // Default to 5 or 10 if all zero to prevent division by zero
  const maxVolume = rawMaxVolume > 0 ? Math.ceil(rawMaxVolume * 1.15) : 5;

  const count = timeline.length;
  const colWidth = plotWidth / count;
  const barWidth = Math.max(4, Math.min(28, colWidth * 0.55));

  const bars = [];
  const scorePoints = [];
  const scoreSegments = [];
  let currentSegment = [];

  for (let i = 0; i < count; i += 1) {
    const day = timeline[i];
    const val = volumes[i];
    const centerX = padding.left + i * colWidth + colWidth / 2;

    // Bar coordinates
    const barHeight = (val / maxVolume) * plotHeight;
    const barY = padding.top + plotHeight - barHeight;
    const barX = centerX - barWidth / 2;

    bars.push({
      date: day.date,
      dateLabel: formatUtcDate(day.date, false),
      fullDateLabel: formatUtcDate(day.date, true),
      x: barX,
      y: barY,
      width: barWidth,
      height: barHeight,
      value: val,
    });

    // Score trend line coordinates
    const avgScore = day.average_score;
    const hasScore = isFiniteNumber(avgScore) && Number(avgScore) >= 0;

    if (hasScore) {
      // Score is 0.0 to 1.0 mapped to plotHeight
      const scoreClamped = Math.min(1.0, Math.max(0.0, avgScore));
      const scoreY = padding.top + plotHeight - scoreClamped * plotHeight;
      const point = {
        x: centerX,
        y: scoreY,
        score: avgScore,
        scorePercent: `${Math.round(scoreClamped * 100)}%`,
        date: day.date,
        dateLabel: formatUtcDate(day.date, false),
      };

      scorePoints.push(point);
      currentSegment.push(`${centerX.toFixed(1)},${scoreY.toFixed(1)}`);
    } else {
      // Missing score: break segment so the line does NOT connect across null days!
      if (currentSegment.length > 0) {
        scoreSegments.push(currentSegment.join(" "));
        currentSegment = [];
      }
    }
  }

  // Push final segment if open
  if (currentSegment.length > 0) {
    scoreSegments.push(currentSegment.join(" "));
  }

  // Generate X axis labels (downsample if > 14 days)
  const xLabels = [];
  const step = count > 14 ? (count > 21 ? 3 : 2) : 1;
  for (let i = 0; i < count; i += step) {
    const centerX = padding.left + i * colWidth + colWidth / 2;
    xLabels.push({
      x: centerX,
      label: formatUtcDate(timeline[i].date, false),
      date: timeline[i].date,
    });
  }

  return {
    isEmpty: false,
    bars,
    scoreSegments,
    scorePoints,
    xLabels,
    maxVolume,
    width,
    height,
    padding,
  };
}

/**
 * Returns a stable string scope for an Identity: "${identity.type}:${identity.id}".
 * Returns null if identity is null, unverified, or missing type/id.
 */
export function getIdentityScope(identity) {
  if (!identity || typeof identity !== "object") {
    return null;
  }
  if (!identity.type || !identity.id) {
    return null;
  }
  return `${identity.type}:${identity.id}`;
}

export const VALID_MODES = new Set(["practice", "quiz", "flashcards"]);
export const VALID_DIFFICULTIES = new Set(["beginner", "intermediate", "advanced"]);
export const VALID_QUESTION_TYPES = new Set(["multiple_choice", "open_ended", "mixed"]);

/**
 * Validates a pending launcher payload to ensure it conforms strictly to Revision creation constraints.
 * Rejects malformed payloads rather than silently altering or defaulting them.
 */
export function validatePendingLaunchPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  // 1. document_ids: must be a non-empty array of 1-10 valid, non-empty string IDs.
  // Reject the entire payload if any supplied ID is invalid. Do not filter invalid entries and continue.
  if (!Array.isArray(payload.document_ids) || payload.document_ids.length === 0 || payload.document_ids.length > 10) {
    return null;
  }
  const docIds = [];
  for (const id of payload.document_ids) {
    if (typeof id !== "string" || !id.trim()) {
      return null;
    }
    docIds.push(id.trim());
  }

  // 2. Validate mode against supported values (reject invalid instead of replacing with defaults)
  if (!payload.mode || !VALID_MODES.has(payload.mode)) {
    return null;
  }

  // 3. Validate difficulty against supported values (reject invalid instead of replacing with defaults)
  if (!payload.difficulty || !VALID_DIFFICULTIES.has(payload.difficulty)) {
    return null;
  }

  // 4. Validate question_type against supported values (reject invalid instead of replacing with defaults)
  if (!payload.question_type || !VALID_QUESTION_TYPES.has(payload.question_type)) {
    return null;
  }

  // 5. Validate question_count against bounds (reject out-of-range or invalid instead of clamping)
  const rawCount = payload.question_count;
  let questionCount = rawCount;
  if (typeof rawCount === "string" && /^\d+$/.test(rawCount.trim())) {
    questionCount = Number.parseInt(rawCount.trim(), 10);
  }
  if (
    typeof questionCount !== "number" ||
    !Number.isInteger(questionCount) ||
    questionCount < 1 ||
    questionCount > 20
  ) {
    return null;
  }

  // 6. Validate topic_focus: null/absent or a valid string no longer than 100 characters.
  // Do not silently truncate malformed payload values.
  let topicFocus = null;
  if (payload.topic_focus !== null && payload.topic_focus !== undefined) {
    if (typeof payload.topic_focus !== "string") {
      return null;
    }
    const trimmed = payload.topic_focus.trim();
    if (trimmed.length > 100) {
      return null;
    }
    topicFocus = trimmed.length > 0 ? trimmed : null;
  }

  return {
    document_ids: docIds,
    mode: payload.mode,
    difficulty: payload.difficulty,
    question_count: questionCount,
    question_type: payload.question_type,
    topic_focus: topicFocus,
  };
}

const STORAGE_LAUNCH_KEY = "learnflow_pending_revision_launch_v3";
let memoryPendingLaunch = null;

/**
 * Saves a validated Revision launcher payload bound to the active identity scope.
 */
export function savePendingRevisionLaunch(payload, identity) {
  const scope = getIdentityScope(identity);
  if (!scope) {
    return false;
  }

  const validated = validatePendingLaunchPayload(payload);
  if (!validated) {
    return false;
  }

  const itemToStore = {
    scope,
    payload: validated,
    savedAt: Date.now(),
  };

  memoryPendingLaunch = itemToStore;

  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.setItem(STORAGE_LAUNCH_KEY, JSON.stringify(itemToStore));
    }
  } catch {
    // Memory fallback suffices if sessionStorage throws or is restricted
  }

  return true;
}

/**
 * Consumes a pending Revision launcher payload for the calling identity.
 *
 * Rules:
 * - If identity scope cannot be verified (e.g. still loading), returns null WITHOUT
 *   clearing the stored payload prematurely, allowing retry once identity resolves.
 * - Once identity is verified, performs one-shot consume-and-clear.
 * - If stored scope does not match current identity, discards payload and returns null.
 */
export function consumePendingRevisionLaunch(identity) {
  const currentScope = getIdentityScope(identity);
  if (!currentScope) {
    // Identity unresolved / unverified; do not discard yet!
    return null;
  }

  let storedItem = memoryPendingLaunch;

  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      const serialized = window.sessionStorage.getItem(STORAGE_LAUNCH_KEY);
      if (serialized) {
        storedItem = JSON.parse(serialized);
      }
    }
  } catch {
    // Fall back to memory item
  }

  // Clear one-shot immediately
  memoryPendingLaunch = null;
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.removeItem(STORAGE_LAUNCH_KEY);
    }
  } catch {
    // Ignore clear error
  }

  if (!storedItem || typeof storedItem !== "object") {
    return null;
  }

  if (storedItem.scope !== currentScope) {
    // Identity mismatch: payload saved under different identity
    return null;
  }

  return validatePendingLaunchPayload(storedItem.payload);
}

/**
 * Constructs a launcher payload from an adaptive recommendation item.
 * Treats recommendation.action_payload as authoritative.
 */
export function createLaunchPayloadFromRecommendation(recommendation) {
  if (!recommendation || typeof recommendation !== "object") {
    return null;
  }

  if (recommendation.action_payload) {
    return validatePendingLaunchPayload(recommendation.action_payload);
  }

  return validatePendingLaunchPayload({
    document_ids: recommendation.document_id ? [recommendation.document_id] : [],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: recommendation.topic_focus || null,
  });
}

/**
 * Constructs a launcher payload for targeted weak-topic practice.
 */
export function createLaunchPayloadFromWeakTopic(weakTopic) {
  if (!weakTopic || !weakTopic.document_id) {
    return null;
  }

  return validatePendingLaunchPayload({
    document_ids: [weakTopic.document_id],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: weakTopic.topic_display || weakTopic.topic_key || null,
  });
}

/**
 * Constructs a launcher payload for spaced-repetition review.
 */
export function createLaunchPayloadFromSchedule(schedule) {
  if (!schedule || !schedule.document_id) {
    return null;
  }

  return validatePendingLaunchPayload({
    document_ids: [schedule.document_id],
    mode: "practice",
    difficulty: "intermediate",
    question_count: 5,
    question_type: "multiple_choice",
    topic_focus: null,
  });
}

/**
 * Strictly validates all required document IDs against hydrated library documents.
 * Zero silent drops, zero partial sets, zero substitutions:
 * If ANY document is missing, archived, not ready, or empty, the entire set is rejected.
 *
 * @param {Array<string>} requiredDocIds
 * @param {Array<Object>} hydratedDocs
 * @returns {Object} Validation outcome
 */
export function validateHydratedDocumentsForLaunch(requiredDocIds = [], hydratedDocs = []) {
  if (!Array.isArray(requiredDocIds) || requiredDocIds.length === 0) {
    return {
      isValid: false,
      validDocs: [],
      missingIds: [],
      unreadyDocs: [],
      reason: "No documents specified for revision.",
    };
  }

  const docMap = new Map();
  for (const doc of hydratedDocs || []) {
    if (doc && doc.id) {
      docMap.set(doc.id, doc);
    }
  }

  const validDocs = [];
  const missingIds = [];
  const unreadyDocs = [];

  for (const docId of requiredDocIds) {
    const doc = docMap.get(docId);
    if (!doc) {
      missingIds.push(docId);
      continue;
    }

    const isReady = doc.status === "ready";
    const hasText = (doc.character_count ?? 0) > 0;
    const isArchived = Boolean(doc.is_archived || doc.archived);

    if (!isReady || !hasText || isArchived) {
      unreadyDocs.push(doc);
    } else {
      validDocs.push(doc);
    }
  }

  if (missingIds.length > 0) {
    return {
      isValid: false,
      validDocs: [],
      missingIds,
      unreadyDocs,
      reason: `Required document (${missingIds.length} missing) could not be found in your library.`,
    };
  }

  if (unreadyDocs.length > 0) {
    const unreadyName = unreadyDocs[0].original_filename || "Document";
    return {
      isValid: false,
      validDocs: [],
      missingIds,
      unreadyDocs,
      reason: `Required document "${unreadyName}" is not ready or has no readable text.`,
    };
  }

  return {
    isValid: true,
    validDocs,
    missingIds: [],
    unreadyDocs: [],
    reason: null,
  };
}
