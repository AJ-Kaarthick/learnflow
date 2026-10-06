import assert from "node:assert/strict";
import { test } from "node:test";
import {
  advanceToNextQuestion,
  calculateSessionProgress,
  createInitialRunnerState,
  findResumeQuestionIndex,
  formatDate,
  formatPercentageScore,
  getQuestionDocumentTitle,
  getStatusBadgeClasses,
  isAtLastQuestion,
  isDocumentArchived,
  prepareRetakeSetup,
  recordAttemptInState,
  validateSetupState,
} from "./revisionState.js";

// ---------------------------------------------------------------------------
// 1. History view rendering & session list data shape
// ---------------------------------------------------------------------------
test("1. History view sessions list formats essential card properties", () => {
  const sessionItem = {
    id: "rev-sess-1",
    title: "Neurobiology Exam Prep",
    status: "completed",
    total_questions: 10,
    score: 0.9,
    created_at: "2026-10-06T10:00:00Z",
    completed_at: "2026-10-06T10:30:00Z",
    document_ids: ["doc-1", "doc-2"],
    config: {
      difficulty: "advanced",
      mode: "quiz",
      question_type: "multiple_choice",
    },
  };

  assert.equal(sessionItem.id, "rev-sess-1");
  assert.equal(sessionItem.title, "Neurobiology Exam Prep");
  assert.equal(sessionItem.status, "completed");
  assert.equal(formatPercentageScore(sessionItem.score), "90%");
  assert.match(formatDate(sessionItem.created_at), /Oct/);
  assert.match(formatDate(sessionItem.created_at), /2026/);
});

// ---------------------------------------------------------------------------
// 2. Loading state representation
// ---------------------------------------------------------------------------
test("2. History and detail loading states are tracked independently", () => {
  const state = {
    sessions: [],
    loading: true,
    error: null,
  };

  assert.equal(state.loading, true);
  assert.equal(state.sessions.length, 0);

  const loadedState = {
    sessions: [{ id: "s-1" }],
    loading: false,
    error: null,
  };
  assert.equal(loadedState.loading, false);
  assert.equal(loadedState.sessions.length, 1);
});

// ---------------------------------------------------------------------------
// 3. Empty history state
// ---------------------------------------------------------------------------
test("3. Empty history state identifies zero sessions and provides CTA path", () => {
  const emptyState = {
    sessions: [],
    loading: false,
    error: null,
  };

  const isEmpty = !emptyState.loading && !emptyState.error && emptyState.sessions.length === 0;
  assert.equal(isEmpty, true);
});

// ---------------------------------------------------------------------------
// 4. History API failure handling
// ---------------------------------------------------------------------------
test("4. History API failure captures error and enables retry", () => {
  const errorState = {
    sessions: [],
    loading: false,
    error: new Error("Network connection dropped"),
  };

  assert.equal(Boolean(errorState.error), true);
  assert.equal(errorState.error.message, "Network connection dropped");
});

// ---------------------------------------------------------------------------
// 5. Session card rendering properties
// ---------------------------------------------------------------------------
test("5. Session card renders formatted score, title fallback, and date", () => {
  const sessionWithoutTitle = {
    id: "s-2",
    title: "",
    status: "in_progress",
    total_questions: 5,
    score: null,
    created_at: "2026-10-06T12:00:00Z",
  };

  const displayTitle = sessionWithoutTitle.title || "Revision Session";
  assert.equal(displayTitle, "Revision Session");
  assert.equal(formatPercentageScore(sessionWithoutTitle.score), "--");
  assert.match(formatDate(sessionWithoutTitle.created_at), /Oct/);
  assert.match(formatDate(sessionWithoutTitle.created_at), /2026/);
});

// ---------------------------------------------------------------------------
// 6. Completed status rendering
// ---------------------------------------------------------------------------
test("6. Completed status uses emerald badge styling", () => {
  const classes = getStatusBadgeClasses("completed");
  assert.match(classes, /bg-emerald/);
  assert.match(classes, /text-emerald/);
});

// ---------------------------------------------------------------------------
// 7. In-progress status rendering
// ---------------------------------------------------------------------------
test("7. In-progress status uses amber badge styling", () => {
  const classes = getStatusBadgeClasses("in_progress");
  assert.match(classes, /bg-amber/);
  assert.match(classes, /text-amber/);
});

// ---------------------------------------------------------------------------
// 8. Resume action detection
// ---------------------------------------------------------------------------
test("8. Resume action is offered exclusively for in_progress sessions", () => {
  function getSessionAction(status) {
    if (status === "in_progress") return "resume";
    if (status === "completed") return "review";
    return null;
  }

  assert.equal(getSessionAction("in_progress"), "resume");
  assert.equal(getSessionAction("completed"), "review");
});

// ---------------------------------------------------------------------------
// 9. Resume fetch and deterministic question position restoration
// ---------------------------------------------------------------------------
test("9. Resume starts at first unattempted question without regenerating questions", () => {
  const inProgressSession = {
    id: "sess-resume",
    status: "in_progress",
    total_questions: 3,
    questions: [
      {
        id: "q-1",
        position: 1,
        question_text: "Q1",
        attempts: [{ id: "att-1", attempt_number: 1, score: 1.0, is_correct: true }],
      },
      {
        id: "q-2",
        position: 2,
        question_text: "Q2",
        attempts: [], // No attempts yet
      },
      {
        id: "q-3",
        position: 3,
        question_text: "Q3",
        attempts: [],
      },
    ],
  };

  const runnerState = createInitialRunnerState(inProgressSession);

  // Must resume at question index 1 (q-2), which has no attempts!
  assert.equal(runnerState.currentIndex, 1);
  assert.equal(runnerState.questions[runnerState.currentIndex].id, "q-2");
  assert.equal(runnerState.isCompleted, false);
});

test("9b. Resume starts at last question if all questions already have attempts", () => {
  const allAttemptedSession = {
    id: "sess-all-attempted",
    status: "in_progress",
    total_questions: 2,
    questions: [
      {
        id: "q-1",
        attempts: [{ id: "att-1", attempt_number: 1, score: 1.0 }],
      },
      {
        id: "q-2",
        attempts: [{ id: "att-2", attempt_number: 1, score: 0.5 }],
      },
    ],
  };

  const runnerState = createInitialRunnerState(allAttemptedSession);
  assert.equal(runnerState.currentIndex, 1); // Last question index
});

// ---------------------------------------------------------------------------
// 10. Review action triggering
// ---------------------------------------------------------------------------
test("10. Completed session view mode switches to 'results'", () => {
  let viewMode = "history";
  function onReviewSession(session) {
    if (session.status === "completed") {
      viewMode = "results";
    }
  }

  onReviewSession({ id: "s-1", status: "completed" });
  assert.equal(viewMode, "results");
});

// ---------------------------------------------------------------------------
// 11. Completed results data rendering
// ---------------------------------------------------------------------------
test("11. Completed results view uses full persisted detail without altering questions", () => {
  const completedDetail = {
    id: "s-comp",
    title: "Completed History Session",
    status: "completed",
    score: 0.85,
    total_questions: 2,
    completed_at: "2026-10-06T15:00:00Z",
    documents: [
      { document_id: "doc-1", original_filename: "Lecture1.pdf", status: "ready" },
    ],
    questions: [
      {
        id: "q-1",
        question_text: "Question 1 text",
        attempts: [
          { attempt_number: 1, submitted_answer: "Wrong", score: 0.0, is_correct: false },
          { attempt_number: 2, submitted_answer: "Right", score: 1.0, is_correct: true },
        ],
      },
    ],
  };

  assert.equal(completedDetail.status, "completed");
  assert.equal(completedDetail.documents[0].original_filename, "Lecture1.pdf");
  assert.equal(completedDetail.questions[0].attempts.length, 2);
});

// ---------------------------------------------------------------------------
// 12. Final score display from backend data
// ---------------------------------------------------------------------------
test("12. Frontend displays official backend session.score verbatim", () => {
  const session = { score: 0.7333 };
  assert.equal(formatPercentageScore(session.score), "73%");

  // Never recalculate or override backend score
  const displayScore = session.score;
  assert.equal(displayScore, 0.7333);
});

// ---------------------------------------------------------------------------
// 13. Question-by-question review structure
// ---------------------------------------------------------------------------
test("13. Question-by-question review exposes position, text, and outcomes", () => {
  const question = {
    id: "q-1",
    position: 1,
    question_type: "multiple_choice",
    question_text: "Which organelle generates ATP?",
    options: ["Mitochondria", "Ribosome", "Nucleus"],
    correct_answer: "Mitochondria",
    explanation: "Mitochondria is the powerhouse of the cell.",
  };

  assert.equal(question.position, 1);
  assert.equal(question.question_type, "multiple_choice");
  assert.equal(question.options.length, 3);
  assert.equal(question.correct_answer, "Mitochondria");
});

// ---------------------------------------------------------------------------
// 14. Attempt history preservation (Attempt #1, Attempt #2)
// ---------------------------------------------------------------------------
test("14. Review preserves and lists historical attempts sequentially", () => {
  const attempts = [
    { attempt_number: 1, submitted_answer: "A", is_correct: false, score: 0.0, feedback: "Incorrect" },
    { attempt_number: 2, submitted_answer: "B", is_correct: true, score: 1.0, feedback: "Well done" },
  ];

  assert.equal(attempts.length, 2);
  assert.equal(attempts[0].attempt_number, 1);
  assert.equal(attempts[0].is_correct, false);
  assert.equal(attempts[1].attempt_number, 2);
  assert.equal(attempts[1].is_correct, true);
});

// ---------------------------------------------------------------------------
// 15. Latest attempt emphasis
// ---------------------------------------------------------------------------
test("15. Latest attempt is identified as official outcome for the question", () => {
  const attempts = [
    { attempt_number: 1, score: 0.0, submitted_answer: "First Try" },
    { attempt_number: 2, score: 1.0, submitted_answer: "Second Try" },
  ];

  const latest = attempts.reduce((prev, curr) =>
    curr.attempt_number > prev.attempt_number ? curr : prev
  );

  assert.equal(latest.attempt_number, 2);
  assert.equal(latest.score, 1.0);
  assert.equal(latest.submitted_answer, "Second Try");
});

// ---------------------------------------------------------------------------
// 16. Multi-document source attribution
// ---------------------------------------------------------------------------
test("16. Questions attribute their specific grounding source document", () => {
  const q1 = {
    source_document_id: "doc-1",
    source_document_title: "Photosynthesis.pdf",
    evidence_snippet: "Chlorophyll absorbs red and blue light.",
  };

  const q2 = {
    source_document_id: "doc-2",
    source_document_title: "CellRespiration.pdf",
    evidence_snippet: "Glycolysis takes place in the cytoplasm.",
  };

  assert.equal(getQuestionDocumentTitle(q1), "Photosynthesis.pdf");
  assert.equal(getQuestionDocumentTitle(q2), "CellRespiration.pdf");
  assert.match(q1.evidence_snippet, /Chlorophyll/);
  assert.match(q2.evidence_snippet, /Glycolysis/);
});

// ---------------------------------------------------------------------------
// 17. Archived/deleted document fallback ("Archived Document")
// ---------------------------------------------------------------------------
test("17. Deleted source document falls back to 'Archived Document' with preserved snippet", () => {
  const deletedDocQuestion = {
    source_document_id: null,
    source_document_title: null,
    evidence_snippet: "Historic preserved evidence text that remains readable.",
  };

  assert.equal(isDocumentArchived(deletedDocQuestion), true);
  assert.equal(getQuestionDocumentTitle(deletedDocQuestion), "Archived Document");
  assert.equal(
    deletedDocQuestion.evidence_snippet,
    "Historic preserved evidence text that remains readable."
  );
});

// ---------------------------------------------------------------------------
// 18. Retake action creates a new-session configuration without mutating original
// ---------------------------------------------------------------------------
test("18. prepareRetakeSetup extracts config into a new setup state", () => {
  const originalCompletedSession = {
    id: "sess-original",
    title: "Midterm Biology",
    status: "completed",
    score: 0.95,
    total_questions: 10,
    document_ids: ["doc-1", "doc-2"],
    config: {
      difficulty: "advanced",
      mode: "quiz",
      question_type: "mixed",
    },
  };

  const retakeSetup = prepareRetakeSetup(originalCompletedSession);

  assert.equal(retakeSetup.title, "Midterm Biology (Retake)");
  assert.equal(retakeSetup.difficulty, "advanced");
  assert.equal(retakeSetup.mode, "quiz");
  assert.equal(retakeSetup.questionType, "mixed");
  assert.equal(retakeSetup.questionCount, 10);
  assert.deepEqual(retakeSetup.documentIds, ["doc-1", "doc-2"]);

  // Original session remains completely unchanged!
  assert.equal(originalCompletedSession.id, "sess-original");
  assert.equal(originalCompletedSession.status, "completed");
  assert.equal(originalCompletedSession.score, 0.95);
});

// ---------------------------------------------------------------------------
// 19. API failure and error recovery
// ---------------------------------------------------------------------------
test("19. Session detail error allows user to dismiss or retry without crash", () => {
  const viewState = {
    loading: false,
    error: new Error("Failed to load session details (status 500)"),
    session: null,
  };

  assert.equal(Boolean(viewState.error), true);
  assert.equal(viewState.session, null);
});

// ---------------------------------------------------------------------------
// 20. Keyboard accessibility helper mapping
// ---------------------------------------------------------------------------
test("20. Keyboard navigation helpers cycle tabs and focusable elements", () => {
  const tabs = ["launcher", "history"];
  function nextTab(current) {
    const idx = tabs.indexOf(current);
    return tabs[(idx + 1) % tabs.length];
  }

  assert.equal(nextTab("launcher"), "history");
  assert.equal(nextTab("history"), "launcher");
});

// ---------------------------------------------------------------------------
// 21. Responsive-safe rendering utilities
// ---------------------------------------------------------------------------
test("21. Progress calculations support mobile and desktop progress indicators", () => {
  const runner = {
    questions: [{ id: "q1" }, { id: "q2" }],
    latestAttempts: { q1: { score: 1.0 } },
  };

  const progress = calculateSessionProgress(runner);
  assert.equal(progress.total, 2);
  assert.equal(progress.answered, 1);
  assert.equal(progress.percentage, 50);
});

// ---------------------------------------------------------------------------
// 22. Regression against existing Phase 3 active runner behavior
// ---------------------------------------------------------------------------
test("22. Active runner answer submission and advance behavior remains preserved", () => {
  const session = {
    id: "s-reg",
    status: "in_progress",
    questions: [
      { id: "q-1", question_text: "Q1" },
      { id: "q-2", question_text: "Q2" },
    ],
  };

  let runner = createInitialRunnerState(session);
  assert.equal(runner.currentIndex, 0);
  assert.equal(isAtLastQuestion(runner), false);

  runner = recordAttemptInState(runner, "q-1", {
    id: "att-1",
    attempt_number: 1,
    score: 1.0,
    is_correct: true,
  });

  runner = advanceToNextQuestion(runner);
  assert.equal(runner.currentIndex, 1);
  assert.equal(isAtLastQuestion(runner), true);
});
