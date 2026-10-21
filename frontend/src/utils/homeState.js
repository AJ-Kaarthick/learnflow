import { ROUTES } from "../router/useHashRoute.js";

/**
 * Generates a personalized greeting title based on the learner's identity.
 *
 * @param {Object|null} identity - Auth identity object ({ type, id, email })
 * @param {number} [hour] - Optional hour (0-23) for time-of-day greetings
 * @returns {string} Formatted greeting title
 */
export function formatGreetingTitle(identity, hour = null) {
  let prefix = "Welcome";
  if (typeof hour === "number" && !Number.isNaN(hour)) {
    if (hour >= 4 && hour < 12) {
      prefix = "Good morning";
    } else if (hour >= 12 && hour < 17) {
      prefix = "Good afternoon";
    } else {
      prefix = "Good evening";
    }
  }

  if (identity && identity.type === "user" && identity.email) {
    const username = identity.email.split("@")[0];
    return `${prefix}, ${username}`;
  }

  if (identity && identity.type === "guest") {
    return prefix === "Welcome" ? "Welcome to LearnFlow" : `${prefix}, Learner`;
  }

  return "Welcome to LearnFlow";
}

/**
 * Returns an appropriate contextual subtitle for the Home dashboard header.
 *
 * @param {Object|null} identity - Auth identity object
 * @returns {string} Subtitle text
 */
export function getGreetingSubtitle(identity) {
  if (identity && identity.type === "user") {
    return "Pick up where you left off, launch a revision session, or explore your study materials.";
  }
  return "Explore your documents, practice with revision sessions, or ask AI grounded questions.";
}

/**
 * Core workspace quick actions for the 4-way dashboard grid.
 */
export const QUICK_ACTIONS = [
  {
    id: "study",
    route: ROUTES.STUDY,
    title: "Study",
    description: "Summaries, flashcards, quizzes & visual concept maps.",
    badge: "Learn & Visualize",
    ariaLabel: "Navigate to Study workspace",
  },
  {
    id: "revision",
    route: ROUTES.REVISION,
    title: "Revision",
    description: "Targeted practice sessions, exam quizzes & attempt history.",
    badge: "Active Recall",
    ariaLabel: "Navigate to Revision workspace",
  },
  {
    id: "chat",
    route: ROUTES.CHAT,
    title: "Chat",
    description: "Ask questions grounded in one document or your entire library.",
    badge: "Grounded Q&A",
    ariaLabel: "Navigate to Chat workspace",
  },
  {
    id: "progress",
    route: ROUTES.PROGRESS,
    title: "Progress",
    description: "Topic mastery tracking, weak areas & spaced repetition schedules.",
    badge: "Analytics",
    ariaLabel: "Navigate to Progress analytics workspace",
  },
];

/**
 * Formats a document's last opened ISO date string into a readable short date.
 *
 * @param {string|null} isoString
 * @returns {string} Formatted date string (e.g., 'Oct 21, 2026') or '--'
 */
export function formatRecentDocumentDate(isoString) {
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
 * Extracts and sanitizes the most recent in-progress revision session.
 * Excludes completed, abandoned, or malformed sessions.
 *
 * @param {Array<Object>} sessions - List of session summaries or details
 * @returns {Object|null} Sanitized in-progress session descriptor or null
 */
export function extractInProgressSession(sessions) {
  if (!Array.isArray(sessions) || sessions.length === 0) {
    return null;
  }

  const candidate = sessions.find((s) => s && s.status === "in_progress");
  if (!candidate || !candidate.id || typeof candidate.id !== "string") {
    return null;
  }

  const title = typeof candidate.title === "string" && candidate.title.trim()
    ? candidate.title.trim()
    : "Untitled Revision Session";

  const config = candidate.config && typeof candidate.config === "object" ? candidate.config : {};
  const difficulty = candidate.difficulty || config.difficulty || null;
  const mode = candidate.mode || config.mode || null;

  let totalQuestions = null;
  if (typeof candidate.total_questions === "number" && candidate.total_questions > 0) {
    totalQuestions = candidate.total_questions;
  } else if (Array.isArray(candidate.questions) && candidate.questions.length > 0) {
    totalQuestions = candidate.questions.length;
  }

  let answeredQuestions = null;
  if (Array.isArray(candidate.questions)) {
    answeredQuestions = candidate.questions.filter(
      (q) => Array.isArray(q.attempts) && q.attempts.length > 0
    ).length;
  } else if (typeof candidate.answered_questions === "number" && candidate.answered_questions >= 0) {
    answeredQuestions = candidate.answered_questions;
  }

  let progressPercentage = null;
  if (typeof answeredQuestions === "number" && typeof totalQuestions === "number" && totalQuestions > 0) {
    progressPercentage = Math.round((answeredQuestions / totalQuestions) * 100);
  }

  return {
    id: candidate.id,
    title,
    difficulty,
    mode,
    totalQuestions,
    answeredQuestions,
    progressPercentage,
    createdAt: candidate.created_at || null,
  };
}

/**
 * Formats progress text for an in-progress revision session.
 *
 * @param {Object} session - Sanitized session descriptor from extractInProgressSession
 * @returns {string} Human-readable progress description
 */
export function formatInProgressSessionProgress(session) {
  if (!session) {
    return "Revision session in progress";
  }

  if (typeof session.answeredQuestions === "number" && typeof session.totalQuestions === "number" && session.totalQuestions > 0) {
    return `${session.answeredQuestions} of ${session.totalQuestions} questions answered`;
  }

  if (typeof session.totalQuestions === "number" && session.totalQuestions > 0) {
    return `${session.totalQuestions} questions`;
  }

  return "Revision session in progress";
}

/**
 * Sanitizes and limits the top adaptive recommendations strictly preserving
 * the M5 canonical priority order.
 *
 * @param {Array<Object>} recommendations - Raw recommendations from getProgressRecommendations
 * @param {number} [max=2] - Maximum number of recommendations to return
 * @returns {Array<Object>} Sanitized recommendation descriptors
 */
export function getTopRecommendations(recommendations, max = 2) {
  if (!Array.isArray(recommendations) || recommendations.length === 0) {
    return [];
  }

  return recommendations.slice(0, max).map((rec, index) => {
    if (!rec || typeof rec !== "object") {
      return null;
    }

    const type = ["spaced_review", "weak_topic_practice", "unrevised_document"].includes(rec.type)
      ? rec.type
      : "unrevised_document";

    const defaultTitle =
      type === "spaced_review"
        ? "Spaced Review Due"
        : type === "weak_topic_practice"
        ? "Practice Weak Topic"
        : "First Revision";

    const title = typeof rec.title === "string" && rec.title.trim()
      ? rec.title.trim()
      : defaultTitle;

    const reason = typeof rec.reason === "string" && rec.reason.trim()
      ? rec.reason.trim()
      : "Recommended practice based on your learning activity.";

    const documentTitle = typeof rec.document_title === "string" && rec.document_title.trim()
      ? rec.document_title.trim()
      : "Archived Document";

    const documentId = rec.document_id || rec.action_payload?.document_ids?.[0] || null;
    const isArchived = Boolean(rec.is_archived);
    const isActionable = Boolean(rec.is_actionable && !isArchived && documentId);

    const topicFocus =
      typeof rec.topic_focus === "string" && rec.topic_focus.trim()
        ? rec.topic_focus.trim()
        : rec.action_payload?.topic_focus || null;

    const urgency = typeof rec.urgency === "number" ? rec.urgency : null;
    const dueDate = rec.due_date || null;
    const struggleIndex = typeof rec.struggle_index === "number" ? rec.struggle_index : null;
    const masteryScore = typeof rec.mastery_score === "number" ? rec.mastery_score : null;

    return {
      id: rec.id || `rec-${index}`,
      type,
      priority: typeof rec.priority === "number" ? rec.priority : 3,
      title,
      reason,
      documentId,
      documentTitle,
      isArchived,
      isActionable,
      topicFocus,
      urgency,
      dueDate,
      struggleIndex,
      masteryScore,
      actionPayload: rec.action_payload || null,
    };
  }).filter(Boolean);
}

/**
 * Returns badge label and Tailwind styling for recommendation types.
 *
 * @param {string} type - Recommendation type
 * @returns {{ label: string, badgeClasses: string }}
 */
export function getRecommendationBadge(type) {
  switch (type) {
    case "spaced_review":
      return {
        label: "Spaced Review",
        badgeClasses: "bg-amber-50 text-amber-800 border-amber-200",
      };
    case "weak_topic_practice":
      return {
        label: "Weak Topic",
        badgeClasses: "bg-rose-50 text-rose-800 border-rose-200",
      };
    case "unrevised_document":
      return {
        label: "New Document",
        badgeClasses: "bg-blue-50 text-blue-800 border-blue-200",
      };
    default:
      return {
        label: "Recommendation",
        badgeClasses: "bg-slate-50 text-slate-700 border-slate-200",
      };
  }
}

/**
 * Returns action CTA text for a recommendation card.
 *
 * @param {Object} rec - Sanitized recommendation object
 * @returns {string} Action label
 */
export function getRecommendationActionText(rec) {
  if (!rec || !rec.isActionable || rec.isArchived) {
    return rec?.isArchived ? "Archived" : "Not Ready";
  }

  switch (rec.type) {
    case "spaced_review":
      return "Review Now";
    case "weak_topic_practice":
      return "Practice Topic";
    case "unrevised_document":
      return "Start Revision";
    default:
      return "Start Revision";
  }
}

/**
 * Sanitizes and limits the top detected weak topics.
 *
 * @param {Array<Object>} weakTopics - Raw weak topics from getProgressWeakTopics
 * @param {number} [max=2] - Maximum number of items
 * @returns {Array<Object>} Sanitized weak topic descriptors
 */
export function getTopWeakTopics(weakTopics, max = 2) {
  if (!Array.isArray(weakTopics) || weakTopics.length === 0) {
    return [];
  }

  return weakTopics.slice(0, max).map((wt) => {
    if (!wt || typeof wt !== "object") {
      return null;
    }

    const topicDisplay =
      typeof wt.topic_display === "string" && wt.topic_display.trim()
        ? wt.topic_display.trim()
        : typeof wt.topic_key === "string" && wt.topic_key.trim()
        ? wt.topic_key.trim()
        : "Untitled Topic";

    const documentTitle =
      typeof wt.document_title === "string" && wt.document_title.trim()
        ? wt.document_title.trim()
        : "Archived Document";

    const documentId = wt.document_id || null;
    const isArchived = Boolean(wt.is_archived);
    const isActionable = Boolean(wt.is_actionable && !isArchived && documentId);

    const struggleIndex = typeof wt.struggle_index === "number" ? wt.struggle_index : null;
    const masteryScore = typeof wt.mastery_score === "number" ? wt.mastery_score : null;
    const masteryTier = wt.mastery_tier || "needs_practice";
    const totalAttempts = typeof wt.total_attempts === "number" ? wt.total_attempts : 0;
    const distinctQuestions = typeof wt.distinct_attempted_questions === "number" ? wt.distinct_attempted_questions : 0;

    return {
      topicKey: wt.topic_key || topicDisplay,
      topicDisplay,
      documentId,
      documentTitle,
      isArchived,
      isActionable,
      struggleIndex,
      masteryScore,
      masteryTier,
      totalAttempts,
      distinctQuestions,
    };
  }).filter(Boolean);
}
