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
