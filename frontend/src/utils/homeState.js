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
