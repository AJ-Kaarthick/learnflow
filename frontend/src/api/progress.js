import { API_BASE_URL, apiFetch } from "./config.js";
import { parseErrorResponse } from "./errors.js";

/**
 * Retrieves the comprehensive learning intelligence summary for the current identity.
 * Computes decayed mastery, daily activity timelines, difficulty distributions,
 * and flashcard performance on demand.
 *
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<Object>} ProgressSummaryResponse
 */
export async function getProgressSummary(options = {}) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/progress/summary`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load progress summary (status ${response.status})`);
  }

  return response.json();
}

/**
 * Retrieves all topic-level mastery records for the current identity,
 * preserving composite document provenance and recency-decayed scores.
 *
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<Array<Object>>} List of TopicMasteryResponseItem
 */
export async function getProgressTopics(options = {}) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/progress/topics`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load topic mastery (status ${response.status})`);
  }

  return response.json();
}

/**
 * Retrieves detected weak topics for the current identity,
 * ranked deterministically by struggle index and mastery score.
 *
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<Array<Object>>} List of WeakTopicResponseItem
 */
export async function getProgressWeakTopics(options = {}) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/progress/weak-topics`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load weak topics (status ${response.status})`);
  }

  return response.json();
}

/**
 * Retrieves document spaced repetition review schedules for the current identity.
 *
 * @param {Object|boolean} [optionsOrIncludeUnreviewed]
 * @param {boolean} [optionsOrIncludeUnreviewed.includeUnreviewedActive=true]
 * @param {AbortSignal} [optionsOrIncludeUnreviewed.signal]
 * @returns {Promise<Array<Object>>} List of SpacedRepetitionScheduleResponseItem
 */
export async function getSpacedRepetitionSchedules(optionsOrIncludeUnreviewed = {}) {
  let includeUnreviewedActive = true;
  let signal;

  if (typeof optionsOrIncludeUnreviewed === "boolean") {
    includeUnreviewedActive = optionsOrIncludeUnreviewed;
  } else if (optionsOrIncludeUnreviewed && typeof optionsOrIncludeUnreviewed === "object") {
    if (typeof optionsOrIncludeUnreviewed.includeUnreviewedActive === "boolean") {
      includeUnreviewedActive = optionsOrIncludeUnreviewed.includeUnreviewedActive;
    }
    signal = optionsOrIncludeUnreviewed.signal;
  }

  const query = `?include_unreviewed_active=${includeUnreviewedActive ? "true" : "false"}`;
  const response = await apiFetch(`${API_BASE_URL}/api/v1/progress/spaced-repetition${query}`, {
    signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load spaced repetition schedules (status ${response.status})`);
  }

  return response.json();
}

/**
 * Retrieves deterministic adaptive learning recommendations strictly adhering
 * to the M5 priority hierarchy (due review -> weak topic practice -> unrevised document).
 *
 * @param {Object|number|null} [optionsOrLimit]
 * @param {number|null} [optionsOrLimit.limit]
 * @param {AbortSignal} [optionsOrLimit.signal]
 * @returns {Promise<Array<Object>>} List of RecommendationResponseItem
 */
export async function getProgressRecommendations(optionsOrLimit = {}) {
  let limit = null;
  let signal;

  if (typeof optionsOrLimit === "number") {
    limit = optionsOrLimit;
  } else if (optionsOrLimit && typeof optionsOrLimit === "object") {
    if (typeof optionsOrLimit.limit === "number") {
      limit = optionsOrLimit.limit;
    }
    signal = optionsOrLimit.signal;
  }

  const query = limit ? `?limit=${encodeURIComponent(limit)}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/progress/recommendations${query}`, {
    signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load recommendations (status ${response.status})`);
  }

  return response.json();
}
