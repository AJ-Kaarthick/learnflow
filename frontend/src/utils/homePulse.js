import { formatPercentageScore } from "./revisionState.js";

/**
 * Pure state and helper functions for LearnFlow Home Learning Pulse & Recent Activity (V3 Milestone 6 Phase 4).
 *
 * Keeps KPI derivation, overdue schedule counting, activity stream merging,
 * and time formatting deterministic, testable, and completely independent of React rendering.
 */

/**
 * Computes the number of overdue, actionable, unarchived spaced repetition reviews.
 *
 * Requirements:
 * - is_due === true
 * - is_actionable === true
 * - !is_archived
 * - has_history !== false
 *
 * Returns null if schedules is null, undefined, or not an array.
 * Returns 0 if schedules is an array with no due items.
 *
 * @param {Array<Object>|null} schedules - Spaced repetition schedule items
 * @returns {number|null} Overdue reviews count or null
 */
export function calculateOverdueReviewsCount(schedules) {
  if (!Array.isArray(schedules)) {
    return null;
  }

  return schedules.filter(
    (s) =>
      s &&
      s.is_due === true &&
      s.is_actionable === true &&
      !s.is_archived &&
      s.has_history !== false
  ).length;
}

/**
 * Formats a count value into a readable string or '--'.
 *
 * @param {number|null|undefined} count
 * @returns {string} Formatted number or '--'
 */
export function formatKPICount(count) {
  if (count === null || count === undefined || count === "") {
    return "--";
  }
  const num = typeof count === "number" ? count : Number(count);
  if (typeof num === "number" && Number.isFinite(num) && num >= 0) {
    return String(Math.floor(num));
  }
  return "--";
}

/**
 * Formats an accuracy fraction (0.0 to 1.0) into a percentage string (e.g., '85%').
 * Returns '--' if totalAttempts is 0 or unassessed, avoiding fabricating 0%.
 *
 * @param {number|null|undefined} accuracy - Fraction between 0.0 and 1.0
 * @param {number|null|undefined} totalAttempts - Total question attempts
 * @returns {string} Formatted percentage or '--'
 */
export function formatKPIAccuracy(accuracy, totalAttempts) {
  const attempts = typeof totalAttempts === "number" ? totalAttempts : Number(totalAttempts);
  if (!Number.isFinite(attempts) || attempts <= 0) {
    return "--";
  }

  if (accuracy === null || accuracy === undefined || accuracy === "") {
    return "--";
  }

  const num = typeof accuracy === "number" ? accuracy : Number(accuracy);
  if (!Number.isFinite(num)) {
    return "--";
  }

  return `${Math.round(num * 100)}%`;
}

/**
 * Extracts and formats the 4 canonical Home Dashboard Learning Pulse KPIs:
 * 1. Questions Attempted (summary.total_attempted_questions)
 * 2. Overdue Reviews (calculated from schedules)
 * 3. Attempt Accuracy (summary.overall_attempt_accuracy)
 * 4. Completed Revision Sessions (summary.total_completed_sessions)
 *
 * @param {Object|null} summary - ProgressSummaryResponse
 * @param {Array<Object>|null} schedules - Spaced repetition schedule items
 * @returns {Object} Structured KPI objects with labels, formatted values, and metadata
 */
export function extractLearningPulseKPIs(summary, schedules) {
  const overdueCount = calculateOverdueReviewsCount(schedules);

  return {
    questionsAttempted: {
      id: "questions_attempted",
      label: "Questions Attempted",
      value: formatKPICount(summary?.total_attempted_questions),
      raw: typeof summary?.total_attempted_questions === "number" ? summary.total_attempted_questions : null,
      description: "Distinct questions practiced",
    },
    overdueReviews: {
      id: "overdue_reviews",
      label: "Overdue Reviews",
      value: overdueCount !== null ? String(overdueCount) : "--",
      raw: overdueCount,
      description: "Spaced reviews due",
    },
    attemptAccuracy: {
      id: "attempt_accuracy",
      label: "Attempt Accuracy",
      value: formatKPIAccuracy(summary?.overall_attempt_accuracy, summary?.total_attempts),
      raw:
        typeof summary?.total_attempts === "number" &&
        summary.total_attempts > 0 &&
        typeof summary?.overall_attempt_accuracy === "number" &&
        Number.isFinite(summary.overall_attempt_accuracy)
          ? summary.overall_attempt_accuracy
          : null,
      description: "Overall attempt success",
    },
    completedSessions: {
      id: "completed_sessions",
      label: "Completed Sessions",
      value: formatKPICount(summary?.total_completed_sessions),
      raw: typeof summary?.total_completed_sessions === "number" ? summary.total_completed_sessions : null,
      description: "Finished revision sessions",
    },
  };
}

/**
 * Formats an ISO timestamp into a readable date string (e.g. 'Oct 22, 2026').
 *
 * @param {string|null} isoString
 * @returns {string} Formatted date string or '--'
 */
export function formatActivityDate(isoString) {
  if (!isoString) {
    return "--";
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Merges completed Revision sessions and document interactions into a unified,
 * chronologically sorted activity feed.
 *
 * Rules:
 * - Only includes completed revision sessions (status === 'completed' with completed_at).
 * - Document activity with last_opened_at is labeled 'Studied'.
 * - Document activity with no last_opened_at but created_at is labeled 'Uploaded'.
 * - Never labels upload time as study time.
 * - Sorts descending by ISO timestamp.
 * - Limits the output to max items.
 *
 * @param {Object} params
 * @param {Array<Object>} [params.documents=[]] - Documents list
 * @param {Array<Object>} [params.sessions=[]] - Revision sessions list
 * @param {number} [params.limit=5] - Maximum number of items
 * @returns {Array<Object>} Chronological activity feed items
 */
export function mergeRecentLearningActivity({ documents = [], sessions = [], limit = 5 } = {}) {
  const items = [];

  // 1. Process completed revision sessions
  if (Array.isArray(sessions)) {
    for (const session of sessions) {
      if (!session || session.status !== "completed" || !session.completed_at) {
        continue;
      }
      const parsedTime = new Date(session.completed_at).getTime();
      if (Number.isNaN(parsedTime)) {
        continue;
      }

      const mode = session.config?.mode || session.mode || "practice";
      const title =
        typeof session.title === "string" && session.title.trim()
          ? session.title.trim()
          : "Untitled Revision Session";

      items.push({
        id: session.id,
        type: "revision",
        title,
        badgeLabel: mode.charAt(0).toUpperCase() + mode.slice(1),
        score: typeof session.score === "number" ? formatPercentageScore(session.score) : "--",
        rawScore: typeof session.score === "number" ? session.score : null,
        timestamp: session.completed_at,
        parsedTime,
      });
    }
  }

  // 2. Process documents
  if (Array.isArray(documents)) {
    for (const doc of documents) {
      if (!doc || !doc.id) {
        continue;
      }

      const filename =
        typeof doc.original_filename === "string" && doc.original_filename.trim()
          ? doc.original_filename.trim()
          : "Untitled Document";

      if (doc.last_opened_at) {
        const parsedTime = new Date(doc.last_opened_at).getTime();
        if (!Number.isNaN(parsedTime)) {
          items.push({
            id: doc.id,
            type: "document",
            title: filename,
            badgeLabel: "Studied",
            score: null,
            rawScore: null,
            timestamp: doc.last_opened_at,
            parsedTime,
          });
        }
      } else if (doc.created_at) {
        const parsedTime = new Date(doc.created_at).getTime();
        if (!Number.isNaN(parsedTime)) {
          items.push({
            id: doc.id,
            type: "document",
            title: filename,
            badgeLabel: "Uploaded",
            score: null,
            rawScore: null,
            timestamp: doc.created_at,
            parsedTime,
          });
        }
      }
    }
  }

  // 3. Sort chronologically descending
  items.sort((a, b) => b.parsedTime - a.parsedTime);

  return items.slice(0, Math.max(1, limit));
}
