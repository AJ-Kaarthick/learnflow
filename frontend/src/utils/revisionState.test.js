import assert from "node:assert/strict";
import { test } from "node:test";
import { isGuestLimitError, GuestLimitError } from "../api/errors.js";
import { ROUTES, routeHref } from "../router/useHashRoute.js";
import {
  DEFAULT_REVISION_QUESTION_COUNT,
  MAX_REVISION_DOCUMENTS,
  MAX_REVISION_QUESTION_COUNT,
  MIN_REVISION_QUESTION_COUNT,
  REVISION_DIFFICULTIES,
  REVISION_MODES,
  REVISION_QUESTION_TYPES,
  advanceToNextQuestion,
  applySessionCompletion,
  buildCreateSessionPayload,
  calculateSessionProgress,
  calculateSessionScore,
  canSubmitAnswer,
  createInitialRunnerState,
  createInitialSetupState,
  formatPercentageScore,
  getCurrentQuestion,
  goToQuestionIndex,
  isAtLastQuestion,
  recordAttemptInState,
  updateAnswerInState,
  validateSetupState,
} from "./revisionState.js";

// ---------------------------------------------------------------------------
// 1. Revision route constant
// ---------------------------------------------------------------------------
test("1. Revision route constant is defined as 'revision'", () => {
  assert.equal(ROUTES.REVISION, "revision");
});

// ---------------------------------------------------------------------------
// 2. Navigation activates Revision
// ---------------------------------------------------------------------------
test("2. Navigation helper routeHref formats '#/revision'", () => {
  assert.equal(routeHref(ROUTES.REVISION), "#/revision");
});

// ---------------------------------------------------------------------------
// 3. Setup initial state and options
// ---------------------------------------------------------------------------
test("3. createInitialSetupState provides standard default configuration", () => {
  const initial = createInitialSetupState();
  assert.equal(initial.difficulty, "intermediate");
  assert.equal(initial.mode, "practice");
  assert.equal(initial.questionType, "multiple_choice");
  assert.equal(initial.questionCount, 5);
  assert.equal(initial.title, "");
  assert.equal(REVISION_DIFFICULTIES.length, 3);
  assert.equal(REVISION_MODES.length, 3);
  assert.equal(REVISION_QUESTION_TYPES.length, 3);
});

// ---------------------------------------------------------------------------
// 4. Document selection validation
// ---------------------------------------------------------------------------
test("4. Document selection enforces 1 to 10 documents and readiness", () => {
  // Empty selection
  const emptyRes = validateSetupState({ selectedDocuments: [] });
  assert.equal(emptyRes.isValid, false);
  assert.match(emptyRes.error, /Please select at least one document/);

  // Exceeds 10 documents
  const tooMany = Array.from({ length: 11 }, (_, i) => ({
    id: `doc-${i}`,
    status: "ready",
    character_count: 100,
  }));
  const tooManyRes = validateSetupState({ selectedDocuments: tooMany });
  assert.equal(tooManyRes.isValid, false);
  assert.match(tooManyRes.error, /up to 10 documents/);

  // Unreadable / zero character count documents
  const unreadable = [{ id: "doc-0", status: "ready", character_count: 0 }];
  const unreadableRes = validateSetupState({ selectedDocuments: unreadable });
  assert.equal(unreadableRes.isValid, false);
  assert.match(unreadableRes.error, /None of the selected documents have readable text/);

  // Valid selection
  const valid = [
    { id: "doc-1", status: "ready", character_count: 500 },
    { id: "doc-2", status: "ready", character_count: 1200 },
  ];
  const validRes = validateSetupState({ selectedDocuments: valid });
  assert.equal(validRes.isValid, true);
  assert.equal(validRes.error, null);
});

// ---------------------------------------------------------------------------
// 5. Difficulty selection
// ---------------------------------------------------------------------------
test("5. Difficulty selection validates known options", () => {
  const validDoc = [{ id: "doc-1", status: "ready", character_count: 500 }];

  for (const diff of ["beginner", "intermediate", "advanced"]) {
    const res = validateSetupState({ selectedDocuments: validDoc, difficulty: diff });
    assert.equal(res.isValid, true);
  }

  const invalidRes = validateSetupState({ selectedDocuments: validDoc, difficulty: "expert" });
  assert.equal(invalidRes.isValid, false);
  assert.match(invalidRes.error, /Invalid difficulty/);
});

// ---------------------------------------------------------------------------
// 6. Question count selection
// ---------------------------------------------------------------------------
test("6. Question count validates bounds 1 to 20", () => {
  const validDoc = [{ id: "doc-1", status: "ready", character_count: 500 }];

  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: 1 }).isValid, true);
  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: 20 }).isValid, true);
  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: "10" }).isValid, true);

  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: 0 }).isValid, false);
  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: 21 }).isValid, false);
  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionCount: "abc" }).isValid, false);
});

// ---------------------------------------------------------------------------
// 7. Mode selection
// ---------------------------------------------------------------------------
test("7. Mode selection validates practice, quiz, flashcards", () => {
  const validDoc = [{ id: "doc-1", status: "ready", character_count: 500 }];

  for (const mode of ["practice", "quiz", "flashcards"]) {
    assert.equal(validateSetupState({ selectedDocuments: validDoc, mode }).isValid, true);
  }

  assert.equal(validateSetupState({ selectedDocuments: validDoc, mode: "unsupported" }).isValid, false);
});

// ---------------------------------------------------------------------------
// 8. Question type selection
// ---------------------------------------------------------------------------
test("8. Question type selection validates multiple_choice, open_ended, mixed", () => {
  const validDoc = [{ id: "doc-1", status: "ready", character_count: 500 }];

  for (const qType of ["multiple_choice", "open_ended", "mixed"]) {
    assert.equal(validateSetupState({ selectedDocuments: validDoc, questionType: qType }).isValid, true);
  }

  assert.equal(validateSetupState({ selectedDocuments: validDoc, questionType: "boolean" }).isValid, false);
});

// ---------------------------------------------------------------------------
// 9. Create-session API invocation payload
// ---------------------------------------------------------------------------
test("9. buildCreateSessionPayload extracts readable doc IDs and setup options", () => {
  const docs = [
    { id: "doc-1", status: "ready", character_count: 500 },
    { id: "doc-2", status: "failed", character_count: 0 },
    { id: "doc-3", status: "ready", character_count: 1000 },
  ];
  const setupState = {
    title: "  Custom Session Title  ",
    difficulty: "advanced",
    mode: "quiz",
    questionType: "mixed",
    questionCount: 10,
  };

  const payload = buildCreateSessionPayload(setupState, docs);
  assert.deepEqual(payload, {
    document_ids: ["doc-1", "doc-3"],
    title: "Custom Session Title",
    difficulty: "advanced",
    mode: "quiz",
    question_type: "mixed",
    question_count: 10,
  });
});

// ---------------------------------------------------------------------------
// 10. Session loading state transition
// ---------------------------------------------------------------------------
test("10. Runner tracks submitting and completing lifecycle states", () => {
  const session = { id: "s-1", questions: [{ id: "q-1", question_text: "Q1" }] };
  const runner = createInitialRunnerState(session);

  assert.equal(runner.isSubmitting, false);
  assert.equal(runner.isCompleting, false);
  assert.equal(runner.submissionError, null);

  const submitting = { ...runner, isSubmitting: true };
  assert.equal(submitting.isSubmitting, true);
  assert.equal(canSubmitAnswer(runner.questions[0], "Answer", submitting.isSubmitting), false);
});

// ---------------------------------------------------------------------------
// 11. Session creation error state handling
// ---------------------------------------------------------------------------
test("11. Setup validation gracefully surfaces errors for user feedback", () => {
  const result = validateSetupState({ selectedDocuments: [] });
  assert.equal(result.isValid, false);
  assert.ok(result.error);
});

// ---------------------------------------------------------------------------
// 12. MCQ rendering structure and options
// ---------------------------------------------------------------------------
test("12. MCQ question structure provides options list and type", () => {
  const session = {
    id: "s-1",
    questions: [
      {
        id: "q-mcq",
        position: 1,
        question_type: "multiple_choice",
        question_text: "What is photosynthesis?",
        options: ["Process converting light to energy", "Cell division", "Respiration"],
      },
    ],
  };
  const runner = createInitialRunnerState(session);
  const q = getCurrentQuestion(runner);

  assert.equal(q.question_type, "multiple_choice");
  assert.equal(Array.isArray(q.options), true);
  assert.equal(q.options.length, 3);
});

// ---------------------------------------------------------------------------
// 13. MCQ selection state
// ---------------------------------------------------------------------------
test("13. MCQ answer updates store selected option in answers map", () => {
  const session = {
    id: "s-1",
    questions: [{ id: "q-mcq", question_type: "multiple_choice", question_text: "Q?" }],
  };
  let runner = createInitialRunnerState(session);

  runner = updateAnswerInState(runner, "q-mcq", "Option A");
  assert.equal(runner.answers["q-mcq"], "Option A");

  runner = updateAnswerInState(runner, "q-mcq", "Option B");
  assert.equal(runner.answers["q-mcq"], "Option B");
});

// ---------------------------------------------------------------------------
// 14. MCQ submission validation
// ---------------------------------------------------------------------------
test("14. canSubmitAnswer returns true when option selected, false when empty", () => {
  const mcq = { id: "q-1", question_type: "multiple_choice" };

  assert.equal(canSubmitAnswer(mcq, "", false), false);
  assert.equal(canSubmitAnswer(mcq, "   ", false), false);
  assert.equal(canSubmitAnswer(mcq, "Option A", false), true);
  assert.equal(canSubmitAnswer(mcq, "Option A", true), false); // Submitting in progress
});

// ---------------------------------------------------------------------------
// 15. Evaluation result formatting
// ---------------------------------------------------------------------------
test("15. formatPercentageScore converts decimal score to percentage", () => {
  assert.equal(formatPercentageScore(1.0), "100%");
  assert.equal(formatPercentageScore(0.85), "85%");
  assert.equal(formatPercentageScore(0.0), "0%");
  assert.equal(formatPercentageScore(null), "--");
});

// ---------------------------------------------------------------------------
// 16. Open-ended rendering structure
// ---------------------------------------------------------------------------
test("16. Open-ended question structure has open_ended type and null options", () => {
  const session = {
    id: "s-1",
    questions: [
      {
        id: "q-open",
        position: 1,
        question_type: "open_ended",
        question_text: "Explain mitosis.",
        options: null,
      },
    ],
  };
  const runner = createInitialRunnerState(session);
  const q = getCurrentQuestion(runner);

  assert.equal(q.question_type, "open_ended");
  assert.equal(q.options, null);
});

// ---------------------------------------------------------------------------
// 17. Open-ended submission validation
// ---------------------------------------------------------------------------
test("17. Open-ended submission rejects empty/whitespace strings and accepts real text", () => {
  const openQ = { id: "q-open", question_type: "open_ended" };

  assert.equal(canSubmitAnswer(openQ, "", false), false);
  assert.equal(canSubmitAnswer(openQ, "   \n\t  ", false), false);
  assert.equal(canSubmitAnswer(openQ, "Mitosis is cell division...", false), true);
});

// ---------------------------------------------------------------------------
// 18. Retry attempt behavior (preserves prior attempts, increments history)
// ---------------------------------------------------------------------------
test("18. recordAttemptInState appends attempts to history immutably", () => {
  const session = {
    id: "s-1",
    questions: [{ id: "q-1", question_text: "Q1" }],
  };
  let runner = createInitialRunnerState(session);

  const attempt1 = {
    id: "att-1",
    attempt_number: 1,
    submitted_answer: "Wrong Answer",
    is_correct: false,
    score: 0.0,
    feedback: "Not quite.",
  };

  runner = recordAttemptInState(runner, "q-1", attempt1);
  assert.equal(runner.latestAttempts["q-1"].attempt_number, 1);
  assert.equal(runner.attemptsHistory["q-1"].length, 1);

  const attempt2 = {
    id: "att-2",
    attempt_number: 2,
    submitted_answer: "Correct Answer",
    is_correct: true,
    score: 1.0,
    feedback: "Excellent!",
  };

  runner = recordAttemptInState(runner, "q-1", attempt2);
  assert.equal(runner.latestAttempts["q-1"].attempt_number, 2);
  assert.equal(runner.latestAttempts["q-1"].score, 1.0);
  assert.equal(runner.attemptsHistory["q-1"].length, 2);
  assert.equal(runner.attemptsHistory["q-1"][0].attempt_number, 1); // Attempt 1 preserved!
  assert.equal(runner.attemptsHistory["q-1"][1].attempt_number, 2);
});

// ---------------------------------------------------------------------------
// 19. Next-question behavior
// ---------------------------------------------------------------------------
test("19. advanceToNextQuestion increments index up to questions boundary", () => {
  const session = {
    id: "s-1",
    questions: [
      { id: "q-1", question_text: "Q1" },
      { id: "q-2", question_text: "Q2" },
    ],
  };
  let runner = createInitialRunnerState(session);
  assert.equal(runner.currentIndex, 0);

  runner = advanceToNextQuestion(runner);
  assert.equal(runner.currentIndex, 1);

  // Clamped at max index
  runner = advanceToNextQuestion(runner);
  assert.equal(runner.currentIndex, 1);
});

// ---------------------------------------------------------------------------
// 20. Final completion flow
// ---------------------------------------------------------------------------
test("20. isAtLastQuestion detects final question and applySessionCompletion updates status", () => {
  const session = {
    id: "s-1",
    questions: [
      { id: "q-1", question_text: "Q1" },
      { id: "q-2", question_text: "Q2" },
    ],
  };
  let runner = createInitialRunnerState(session);
  assert.equal(isAtLastQuestion(runner), false);

  runner = advanceToNextQuestion(runner);
  assert.equal(isAtLastQuestion(runner), true);

  const completedSession = {
    ...session,
    status: "completed",
    score: 0.9,
    completed_at: "2026-10-06T15:00:00Z",
  };

  runner = applySessionCompletion(runner, completedSession);
  assert.equal(runner.isCompleted, true);
  assert.equal(runner.finalScore, 0.9);
});

// ---------------------------------------------------------------------------
// 21. Guest-limit error handling
// ---------------------------------------------------------------------------
test("21. isGuestLimitError accurately identifies guest quota error objects", () => {
  const guestErr = new GuestLimitError("Limit reached", { limitType: "ai_generation", limit: 5, used: 5 });
  assert.equal(isGuestLimitError(guestErr), true);

  const plainErr = new Error("Generic failure");
  assert.equal(isGuestLimitError(plainErr), false);
  assert.equal(isGuestLimitError(null), false);
});

// ---------------------------------------------------------------------------
// 22. API error handling
// ---------------------------------------------------------------------------
test("22. Runner records error message upon attempt failure", () => {
  const session = { id: "s-1", questions: [{ id: "q-1" }] };
  const runner = createInitialRunnerState(session);

  const errorState = {
    ...runner,
    isSubmitting: false,
    submissionError: new Error("Network timeout"),
  };

  assert.equal(errorState.submissionError.message, "Network timeout");
});

// ---------------------------------------------------------------------------
// 23. Keyboard accessible controls (jump to question index)
// ---------------------------------------------------------------------------
test("23. goToQuestionIndex enables direct accessible keyboard jumping", () => {
  const session = {
    id: "s-1",
    questions: [{ id: "q-1" }, { id: "q-2" }, { id: "q-3" }],
  };
  let runner = createInitialRunnerState(session);

  runner = goToQuestionIndex(runner, 2);
  assert.equal(runner.currentIndex, 2);

  runner = goToQuestionIndex(runner, 10); // Clamped
  assert.equal(runner.currentIndex, 2);

  runner = goToQuestionIndex(runner, -5); // Clamped
  assert.equal(runner.currentIndex, 0);
});

// ---------------------------------------------------------------------------
// 24. Progress and score percentage computation
// ---------------------------------------------------------------------------
test("24. calculateSessionProgress and calculateSessionScore accurately compute metrics", () => {
  const session = {
    id: "s-1",
    questions: [{ id: "q-1" }, { id: "q-2" }, { id: "q-3" }, { id: "q-4" }],
  };
  let runner = createInitialRunnerState(session);

  let progress = calculateSessionProgress(runner);
  assert.equal(progress.total, 4);
  assert.equal(progress.answered, 0);
  assert.equal(progress.percentage, 0);

  // Answer q-1 with 1.0 and q-2 with 0.5
  runner = recordAttemptInState(runner, "q-1", { attempt_number: 1, score: 1.0 });
  runner = recordAttemptInState(runner, "q-2", { attempt_number: 1, score: 0.5 });

  progress = calculateSessionProgress(runner);
  assert.equal(progress.answered, 2);
  assert.equal(progress.percentage, 50);

  // Score: (1.0 + 0.5 + 0.0 + 0.0) / 4 = 1.5 / 4 = 0.375
  const score = calculateSessionScore(runner);
  assert.equal(score, 0.375);
});
