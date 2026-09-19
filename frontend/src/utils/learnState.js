/**
 * Pure state and helper functions for Learn Mode (V3 Milestone 3).
 * Keeps Learn session transitions, caching, action toggling,
 * and multi-document attribution logic testable and predictable.
 */

export const LEARN_DEPTHS = [
  { id: "overview", label: "Overview", description: "High-level summary of core concepts" },
  { id: "standard", label: "Standard", description: "Balanced depth covering essential topics" },
  { id: "in-depth", label: "In-depth", description: "Thorough deep-dive with technical details" },
];

export const LEARN_ACTIONS = [
  { id: "simplify", label: "Simplify", description: "Explain in simpler terms with intuitive analogies" },
  { id: "elaborate", label: "Deep Dive", description: "Expand with comprehensive technical detail" },
  { id: "example", label: "Example", description: "Illustrate with concrete real-world examples" },
];

/**
 * Creates a clean, empty initial state for a Learn session.
 */
export function createInitialLearnSession(initialDepth = "standard") {
  return {
    outline: null,
    selectedTopicId: null,
    selectedSubtopicId: null,
    topicCache: {},
    activeAction: null,
    activeDepth: initialDepth,
    status: "idle", // "idle" | "generating_outline" | "generating_topic" | "error"
    errorMessage: "",
    generationError: null,
    documentIds: [],
  };
}

/**
 * Produces a unique composite key for caching topic generation results.
 * Allows instant navigation between topics, actions, and depth controls
 * without redundant network calls or duplicate guest quota consumption.
 */
export function getTopicCacheKey(topicId, depth = "standard", action = null) {
  const normalizedTopic = String(topicId ?? "").trim();
  const normalizedDepth = String(depth ?? "standard").trim() || "standard";
  const normalizedAction = action ? String(action).trim() : "default";
  return `${normalizedTopic}::${normalizedDepth}::${normalizedAction}`;
}

/**
 * Updates a session with freshly generated curriculum outline data.
 */
export function applyOutlineResponse(session, outlineResponse) {
  const documentIds = Array.isArray(outlineResponse?.document_ids)
    ? [...outlineResponse.document_ids]
    : [];

  return {
    ...session,
    outline: outlineResponse,
    documentIds,
    topicCache: {},
    selectedTopicId: null,
    selectedSubtopicId: null,
    activeAction: null,
    status: "idle",
    errorMessage: "",
    generationError: null,
  };
}

/**
 * Updates a session with freshly generated topic content, caching it under its composite key.
 */
export function applyTopicResponse(session, topicResponse) {
  const topicId = topicResponse.topic_id;
  const depth = topicResponse.depth || session.activeDepth || "standard";
  const action = topicResponse.action || null;
  const key = getTopicCacheKey(topicId, depth, action);

  const nextCache = {
    ...session.topicCache,
    [key]: topicResponse,
  };

  return {
    ...session,
    topicCache: nextCache,
    selectedTopicId: topicId,
    activeAction: action,
    activeDepth: depth,
    status: "idle",
    errorMessage: "",
    generationError: null,
  };
}

/**
 * Retrieves cached topic content if available for the given topic, depth, and action.
 */
export function getTopicContent(session, topicId, depth = "standard", action = null) {
  if (!session?.topicCache) return null;
  const key = getTopicCacheKey(topicId, depth, action);
  return session.topicCache[key] ?? null;
}

/**
 * Checks whether the current selected document IDs differ from the IDs
 * used when the active curriculum outline was generated.
 */
export function isSelectionOutdated(session, currentDocumentIds = []) {
  if (!session?.outline || !Array.isArray(session.documentIds) || session.documentIds.length === 0) {
    return false;
  }

  const sessionSet = new Set(session.documentIds);
  const currentSet = new Set(currentDocumentIds);

  if (sessionSet.size !== currentSet.size) {
    return true;
  }

  for (const id of sessionSet) {
    if (!currentSet.has(id)) {
      return true;
    }
  }

  return false;
}

/**
 * Formats a list of contributing document filenames for UI attribution.
 */
export function formatContributingDocuments(contributingDocs = []) {
  if (!Array.isArray(contributingDocs) || contributingDocs.length === 0) {
    return "";
  }

  const names = contributingDocs
    .map((doc) => (typeof doc === "string" ? doc : doc?.original_filename))
    .filter(Boolean);

  if (names.length === 0) return "";
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

/**
 * Finds a topic in the outline by ID.
 */
export function findTopicById(outline, topicId) {
  if (!outline?.topics || !topicId) return null;
  return outline.topics.find((t) => t.id === topicId) ?? null;
}

/**
 * Finds a subtopic within a topic by subtopic ID.
 */
export function findSubtopicById(topic, subtopicId) {
  if (!topic?.subtopics || !subtopicId) return null;
  return topic.subtopics.find((s) => s.id === subtopicId) ?? null;
}
