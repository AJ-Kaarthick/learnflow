/**
 * Pure state and helper functions for LearnFlow Revision Experience 2.0 (V3 Milestone 4 Phase 3).
 *
 * Keeps configuration validation, attempt tracking, score calculation,
 * question navigation, and accessibility utilities testable, deterministic,
 * and completely independent of React rendering.
 */

export const REVISION_DIFFICULTIES = [
  { id: "beginner", label: "Beginner", description: "Foundational recall and essential concepts" },
  { id: "intermediate", label: "Intermediate", description: "Balanced conceptual comprehension and application" },
  { id: "advanced", label: "Advanced", description: "In-depth analysis, synthesis, and edge cases" },
];

export const REVISION_MODES = [
  { id: "practice", label: "Practice", description: "Immediate feedback, step-by-step learning, and retry capability" },
  { id: "quiz", label: "Quiz", description: "Structured assessment format with score calculation" },
  { id: "flashcards", label: "Flashcards", description: "Active recall card review format" },
];

export const REVISION_QUESTION_TYPES = [
  { id: "multiple_choice", label: "Multiple Choice", description: "Standard single-select questions with deterministic instant grading" },
  { id: "open_ended", label: "Open Ended", description: "Free-form explanations evaluated by AI against grounded rubrics" },
  { id: "mixed", label: "Mixed", description: "Balanced combination of multiple choice and open-ended questions" },
];

export const MIN_REVISION_QUESTION_COUNT = 1;
export const MAX_REVISION_QUESTION_COUNT = 20;
export const DEFAULT_REVISION_QUESTION_COUNT = 5;
export const MAX_REVISION_DOCUMENTS = 10;

/**
 * Creates the initial setup configuration state for creating a revision session.
 */
export function createInitialSetupState() {
  return {
    title: "",
    difficulty: "intermediate",
    mode: "practice",
    questionType: "multiple_choice",
    questionCount: DEFAULT_REVISION_QUESTION_COUNT,
  };
}

/**
 * Validates a setup configuration before submitting to the backend.
 *
 * @param {Object} params
 * @param {Array<Object>} params.selectedDocuments - Hydrated document objects
 * @param {number} params.questionCount
 * @param {string} params.difficulty
 * @param {string} params.mode
 * @param {string} params.questionType
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateSetupState({
  selectedDocuments = [],
  questionCount = DEFAULT_REVISION_QUESTION_COUNT,
  difficulty = "intermediate",
  mode = "practice",
  questionType = "multiple_choice",
} = {}) {
  if (!Array.isArray(selectedDocuments) || selectedDocuments.length === 0) {
    return {
      isValid: false,
      error: "Please select at least one document for revision.",
    };
  }

  if (selectedDocuments.length > MAX_REVISION_DOCUMENTS) {
    return {
      isValid: false,
      error: `You can select up to ${MAX_REVISION_DOCUMENTS} documents for a revision session.`,
    };
  }

  // Ensure at least one selected document is ready and has readable text
  const readableDocs = selectedDocuments.filter(
    (doc) => doc && doc.status === "ready" && (doc.character_count ?? 0) > 0
  );

  if (readableDocs.length === 0) {
    return {
      isValid: false,
      error: "None of the selected documents have readable text. Please select at least one ready document.",
    };
  }

  const parsedCount = Number.parseInt(questionCount, 10);
  if (
    Number.isNaN(parsedCount) ||
    parsedCount < MIN_REVISION_QUESTION_COUNT ||
    parsedCount > MAX_REVISION_QUESTION_COUNT
  ) {
    return {
      isValid: false,
      error: `Question count must be between ${MIN_REVISION_QUESTION_COUNT} and ${MAX_REVISION_QUESTION_COUNT}.`,
    };
  }

  const validDiffs = new Set(REVISION_DIFFICULTIES.map((d) => d.id));
  if (!validDiffs.has(difficulty)) {
    return {
      isValid: false,
      error: `Invalid difficulty: "${difficulty}".`,
    };
  }

  const validModes = new Set(REVISION_MODES.map((m) => m.id));
  if (!validModes.has(mode)) {
    return {
      isValid: false,
      error: `Invalid mode: "${mode}".`,
    };
  }

  const validTypes = new Set(REVISION_QUESTION_TYPES.map((t) => t.id));
  if (!validTypes.has(questionType)) {
    return {
      isValid: false,
      error: `Invalid question type: "${questionType}".`,
    };
  }

  return { isValid: true, error: null };
}

/**
 * Builds the payload for POST /api/v1/revision/sessions.
 */
export function buildCreateSessionPayload(setupState, selectedDocuments) {
  const documentIds = selectedDocuments
    .filter((doc) => doc && doc.status === "ready" && (doc.character_count ?? 0) > 0)
    .map((doc) => doc.id);

  const payload = {
    document_ids: documentIds,
    difficulty: setupState.difficulty || "intermediate",
    mode: setupState.mode || "practice",
    question_type: setupState.questionType || "multiple_choice",
    question_count: Number.parseInt(setupState.questionCount, 10) || DEFAULT_REVISION_QUESTION_COUNT,
  };

  if (setupState.title && setupState.title.trim()) {
    payload.title = setupState.title.trim();
  }

  return payload;
}

/**
 * Finds the index of the first unattempted question for resuming in-progress sessions.
 * If all questions have attempts, returns the last question index.
 */
export function findResumeQuestionIndex(session, latestAttempts = {}) {
  const questions = session?.questions || [];
  if (questions.length === 0) return 0;
  const firstUnattempted = questions.findIndex((q) => !latestAttempts[q.id]);
  return firstUnattempted !== -1 ? firstUnattempted : questions.length - 1;
}

/**
 * Creates the initial active runner state from a RevisionSessionDetailResponse.
 * For in-progress sessions, deterministically starts at the first unattempted question.
 *
 * @param {Object} session - RevisionSessionDetailResponse
 * @returns {Object} Runner state
 */
export function createInitialRunnerState(session) {
  const questions = Array.isArray(session?.questions) ? [...session.questions] : [];
  const latestAttempts = {};
  const attemptsHistory = {};
  const answers = {};

  for (const q of questions) {
    const attempts = Array.isArray(q.attempts) ? [...q.attempts] : [];
    attemptsHistory[q.id] = attempts;
    if (attempts.length > 0) {
      // Find highest attempt_number
      const latest = attempts.reduce((prev, curr) =>
        (curr.attempt_number ?? 0) > (prev.attempt_number ?? 0) ? curr : prev
      );
      latestAttempts[q.id] = latest;
      answers[q.id] = latest.submitted_answer || "";
    } else {
      answers[q.id] = "";
    }
  }

  // Resume at first unattempted question if in progress
  let startIndex = 0;
  if (session?.status !== "completed" && questions.length > 0) {
    startIndex = findResumeQuestionIndex(session, latestAttempts);
  }

  return {
    session,
    questions,
    currentIndex: startIndex,
    answers,
    latestAttempts,
    attemptsHistory,
    isSubmitting: false,
    submissionError: null,
    isCompleting: false,
    completionError: null,
    isCompleted: session?.status === "completed",
    finalScore: session?.score ?? null,
  };
}

/**
 * Returns the currently active question from runner state.
 */
export function getCurrentQuestion(runnerState) {
  if (!runnerState || !runnerState.questions) return null;
  return runnerState.questions[runnerState.currentIndex] ?? null;
}

/**
 * Checks whether an answer is valid for submission.
 */
export function canSubmitAnswer(question, answer, isSubmitting = false) {
  if (isSubmitting) return false;
  if (!question) return false;
  const cleaned = (answer ?? "").trim();
  return cleaned.length > 0;
}

/**
 * Immutably updates the runner state with a new attempt for a question.
 * Preserves all earlier attempt records in `attemptsHistory`.
 *
 * @param {Object} runnerState
 * @param {string} questionId
 * @param {Object} attempt - RevisionAttemptResponse
 * @returns {Object} Updated runner state
 */
export function recordAttemptInState(runnerState, questionId, attempt) {
  const existingHistory = runnerState.attemptsHistory[questionId] || [];
  const newHistory = [...existingHistory, attempt];

  return {
    ...runnerState,
    isSubmitting: false,
    submissionError: null,
    latestAttempts: {
      ...runnerState.latestAttempts,
      [questionId]: attempt,
    },
    attemptsHistory: {
      ...runnerState.attemptsHistory,
      [questionId]: newHistory,
    },
  };
}

/**
 * Updates the current answer input for a question in runner state.
 */
export function updateAnswerInState(runnerState, questionId, answer) {
  return {
    ...runnerState,
    answers: {
      ...runnerState.answers,
      [questionId]: answer,
    },
  };
}

/**
 * Advances the active question index if not already at the last question.
 */
export function advanceToNextQuestion(runnerState) {
  if (!runnerState || !runnerState.questions) return runnerState;
  const maxIndex = Math.max(0, runnerState.questions.length - 1);
  const nextIndex = Math.min(maxIndex, runnerState.currentIndex + 1);

  return {
    ...runnerState,
    currentIndex: nextIndex,
    submissionError: null,
  };
}

/**
 * Navigates to a specific question index within bounds.
 */
export function goToQuestionIndex(runnerState, index) {
  if (!runnerState || !runnerState.questions) return runnerState;
  const maxIndex = Math.max(0, runnerState.questions.length - 1);
  const safeIndex = Math.max(0, Math.min(maxIndex, index));

  return {
    ...runnerState,
    currentIndex: safeIndex,
    submissionError: null,
  };
}

/**
 * Whether the active question is the final question in the session.
 */
export function isAtLastQuestion(runnerState) {
  if (!runnerState || !runnerState.questions || runnerState.questions.length === 0) return true;
  return runnerState.currentIndex >= runnerState.questions.length - 1;
}

/**
 * Immutably applies the completed session response.
 */
export function applySessionCompletion(runnerState, completedSession) {
  return {
    ...runnerState,
    session: completedSession,
    isCompleting: false,
    completionError: null,
    isCompleted: true,
    finalScore: completedSession.score,
  };
}

/**
 * Calculates current progress summary across the session.
 */
export function calculateSessionProgress(runnerState) {
  if (!runnerState || !runnerState.questions) {
    return { total: 0, answered: 0, percentage: 0 };
  }

  const total = runnerState.questions.length;
  if (total === 0) return { total: 0, answered: 0, percentage: 0 };

  const answered = runnerState.questions.filter(
    (q) => Boolean(runnerState.latestAttempts[q.id])
  ).length;

  const percentage = Math.round((answered / total) * 100);
  return { total, answered, percentage };
}

/**
 * Calculates session score using the latest attempt per question (M4 rule).
 */
export function calculateSessionScore(runnerState) {
  if (!runnerState || !runnerState.questions || runnerState.questions.length === 0) {
    return 0.0;
  }

  let totalScore = 0.0;
  for (const q of runnerState.questions) {
    const attempt = runnerState.latestAttempts[q.id];
    if (attempt && typeof attempt.score === "number") {
      totalScore += Math.max(0.0, Math.min(1.0, attempt.score));
    }
  }

  return Number((totalScore / runnerState.questions.length).toFixed(4));
}

/**
 * Formats a float score (0.0 to 1.0) into a clean percentage string.
 */
export function formatPercentageScore(score) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "--";
  }
  return `${Math.round(score * 100)}%`;
}

/**
 * Returns the source document title or a graceful fallback for archived/deleted documents.
 */
export function getQuestionDocumentTitle(question) {
  if (!question || !question.source_document_title || !question.source_document_id) {
    return "Archived Document";
  }
  return question.source_document_title;
}

/**
 * Whether the question's source document has been deleted/archived.
 */
export function isDocumentArchived(question) {
  return Boolean(!question?.source_document_id || !question?.source_document_title);
}

/**
 * Formats an ISO datetime string into human-readable date.
 */
export function formatDate(isoString) {
  if (!isoString) return "--";
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "--";
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "--";
  }
}

/**
 * Extracts configuration from a completed session to pre-populate setup for a retake.
 * Does not mutate the original session.
 */
export function prepareRetakeSetup(session) {
  if (!session) return createInitialSetupState();
  const config = session.config || {};
  return {
    title: session.title ? `${session.title} (Retake)` : "",
    difficulty: config.difficulty || "intermediate",
    mode: config.mode || "practice",
    questionType: config.question_type || "multiple_choice",
    questionCount: session.total_questions || DEFAULT_REVISION_QUESTION_COUNT,
    documentIds: Array.isArray(session.document_ids) ? [...session.document_ids] : [],
  };
}

/**
 * Returns Tailwind class names for a session status pill.
 */
export function getStatusBadgeClasses(status) {
  if (status === "completed") {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  return "bg-amber-50 text-amber-700 border-amber-200";
}
