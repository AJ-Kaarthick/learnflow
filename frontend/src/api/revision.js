import { API_BASE_URL, apiFetch } from "./config.js";
import { parseErrorResponse } from "./errors.js";

/**
 * Creates a new RevisionSession spanning 1 to 10 documents.
 * Generates grounded questions via AI.
 *
 * @param {Object} params
 * @param {string[]} params.documentIds - 1 to 10 document IDs
 * @param {string} [params.title] - Optional title
 * @param {"beginner"|"intermediate"|"advanced"} [params.difficulty="intermediate"]
 * @param {"practice"|"quiz"|"flashcards"} [params.mode="practice"]
 * @param {"multiple_choice"|"open_ended"|"mixed"} [params.questionType="multiple_choice"]
 * @param {number} [params.questionCount=5] - Number of questions (1-20)
 * @returns {Promise<Object>} Created RevisionSessionDetailResponse
 */
export async function createRevisionSession(options = {}) {
  const documentIds = options.document_ids ?? options.documentIds;
  const questionType = options.question_type ?? options.questionType ?? "multiple_choice";
  const questionCount = options.question_count ?? options.questionCount ?? 5;
  const difficulty = options.difficulty ?? "intermediate";
  const mode = options.mode ?? "practice";
  const title = options.title;

  const payload = {
    document_ids: documentIds,
    difficulty,
    mode,
    question_type: questionType,
    question_count: questionCount,
  };

  if (title && typeof title === "string" && title.trim()) {
    payload.title = title.trim();
  }

  const response = await apiFetch(`${API_BASE_URL}/api/v1/revision/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't generate revision questions right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Revision session creation failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Lists all revision sessions belonging to the current identity, ordered newest first.
 *
 * @returns {Promise<Array<Object>>} List of RevisionSessionSummaryResponse
 */
export async function listRevisionSessions() {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/revision/sessions`);

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load revision sessions (status ${response.status})`);
  }

  return response.json();
}

/**
 * Retrieves full details for a specific revision session, including questions and attempts.
 *
 * @param {string} sessionId
 * @returns {Promise<Object>} RevisionSessionDetailResponse
 */
export async function getRevisionSession(sessionId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/revision/sessions/${sessionId}`);

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not load revision session (status ${response.status})`);
  }

  return response.json();
}

/**
 * Submits an answer attempt for a specific question in an active revision session.
 * Evaluates deterministically for MCQs or via AI for open-ended questions.
 *
 * @param {string} sessionId
 * @param {string} questionId
 * @param {string} submittedAnswer
 * @returns {Promise<Object>} RevisionAttemptResponse
 */
export async function submitRevisionAttempt(sessionId, questionId, submittedAnswer) {
  const response = await apiFetch(
    `${API_BASE_URL}/api/v1/revision/sessions/${sessionId}/questions/${questionId}/attempts`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ submitted_answer: submittedAnswer }),
    }
  );

  if (!response.ok) {
    if (response.status === 502) {
      throw new Error("The AI couldn't evaluate your answer right now. Please try again in a moment.");
    }
    throw await parseErrorResponse(response, `Attempt submission failed (status ${response.status})`);
  }

  return response.json();
}

/**
 * Completes an active revision session, calculates final score from latest attempts,
 * and records completion timestamp.
 *
 * @param {string} sessionId
 * @returns {Promise<Object>} Final RevisionSessionDetailResponse
 */
export async function completeRevisionSession(sessionId) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/revision/sessions/${sessionId}/complete`, {
    method: "POST",
  });

  if (!response.ok) {
    throw await parseErrorResponse(response, `Could not complete revision session (status ${response.status})`);
  }

  return response.json();
}
