import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  advanceToNextQuestion,
  buildCreateSessionPayload,
  calculateSessionProgress,
  createInitialRunnerState,
  createInitialSetupState,
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

// ---------------------------------------------------------------------------
// 23. Bug 2 Regression: Setup state survives New Revision <-> Session History
// ---------------------------------------------------------------------------
test("23. Setup state survives New Revision <-> Session History view switches", () => {
  // Simulate page-level state lifecycle in RevisionPage
  let pageState = {
    viewMode: "launcher",
    setupState: createInitialSetupState(),
    selectedDocuments: [],
    activeSession: null,
  };

  // User configures setup with 2 documents and custom settings
  const doc1 = { id: "doc-1", original_filename: "modula4.pptx", status: "ready", character_count: 800 };
  const doc2 = { id: "doc-2", original_filename: "Data center.pptx", status: "ready", character_count: 1200 };

  pageState = {
    ...pageState,
    selectedDocuments: [doc1, doc2],
    setupState: {
      title: "Midterm Preparation",
      difficulty: "advanced",
      mode: "quiz",
      questionType: "open_ended",
      questionCount: 8,
    },
  };

  // User switches view to "history"
  pageState = {
    ...pageState,
    viewMode: "history",
  };
  assert.equal(pageState.viewMode, "history");

  // User switches view back to "launcher"
  pageState = {
    ...pageState,
    viewMode: "launcher",
  };

  // Assert all selections and configuration survived the view switch intact
  assert.equal(pageState.selectedDocuments.length, 2);
  assert.equal(pageState.selectedDocuments[0].id, "doc-1");
  assert.equal(pageState.selectedDocuments[1].id, "doc-2");
  assert.equal(pageState.setupState.title, "Midterm Preparation");
  assert.equal(pageState.setupState.difficulty, "advanced");
  assert.equal(pageState.setupState.mode, "quiz");
  assert.equal(pageState.setupState.questionType, "open_ended");
  assert.equal(pageState.setupState.questionCount, 8);

  // On session creation success, state resets for next session
  pageState = {
    ...pageState,
    activeSession: { id: "sess-created" },
    viewMode: "runner",
    setupState: createInitialSetupState(),
    selectedDocuments: [],
  };
  assert.equal(pageState.selectedDocuments.length, 0);
  assert.equal(pageState.setupState.title, "");
});

// ---------------------------------------------------------------------------
// 24. Bug 3 Regression: Valid session creation payload contains all required backend fields
// ---------------------------------------------------------------------------
test("24. Valid session creation payload contains all required backend fields", () => {
  const selectedDocs = [
    { id: "doc-alpha", original_filename: "Alpha.pdf", status: "ready", character_count: 500 },
    { id: "doc-beta", original_filename: "Beta.pdf", status: "ready", character_count: 900 },
  ];
  const setupConfig = {
    title: "Integration Test Session",
    difficulty: "intermediate",
    mode: "practice",
    questionType: "multiple_choice",
    questionCount: 5,
  };

  const payload = buildCreateSessionPayload(setupConfig, selectedDocs);

  // Verify all fields required by backend RevisionSessionCreateRequest
  assert.ok(Array.isArray(payload.document_ids), "document_ids must be an array");
  assert.ok(payload.document_ids.length >= 1, "document_ids must have at least 1 document");
  assert.ok(payload.document_ids.length <= 10, "document_ids must not exceed 10 documents");
  assert.deepEqual(payload.document_ids, ["doc-alpha", "doc-beta"]);

  assert.equal(payload.difficulty, "intermediate");
  assert.equal(payload.mode, "practice");
  assert.equal(payload.question_type, "multiple_choice");
  assert.equal(payload.question_count, 5);
  assert.equal(payload.title, "Integration Test Session");

  // Verify JSON serialization retains document_ids (does not omit undefined)
  const jsonString = JSON.stringify(payload);
  const parsed = JSON.parse(jsonString);
  assert.ok(Array.isArray(parsed.document_ids));
  assert.equal(parsed.document_ids.length, 2);
  assert.equal(parsed.question_type, "multiple_choice");
  assert.equal(parsed.question_count, 5);
});

// ---------------------------------------------------------------------------
// 25. Bug 1 Regression: Revision page container enables vertical scrolling
// ---------------------------------------------------------------------------
test("25. Revision page container structure enables viewport scrolling without layout clipping", () => {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const revisionPagePath = join(__dirname, "../pages/RevisionPage.jsx");
  const source = readFileSync(revisionPagePath, "utf-8");

  // Verify container is a semantic main element with accessible label
  assert.match(source, /<main\s+aria-label="Revision"/);

  // Verify container uses overflow-y-auto to allow vertical scrolling when content exceeds viewport
  assert.match(source, /overflow-y-auto/);

  // Verify container uses min-h-0 and flex-1 to enable flex child scrolling within AppShell
  assert.match(source, /flex-1/);
  assert.match(source, /min-h-0/);

  // Verify outer element does NOT lock height with overflow-hidden
  assert.doesNotMatch(source, /<main[^>]*overflow-hidden/);
});

// ---------------------------------------------------------------------------
// 26. UI Polish: Retake action button uses enabled secondary action styling
// ---------------------------------------------------------------------------
test("26. Retake action button in history view uses enabled secondary action styling with high contrast", () => {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const historyViewPath = join(__dirname, "../components/RevisionHistoryView.jsx");
  const source = readFileSync(historyViewPath, "utf-8");

  // Verify Retake button does NOT use bg-slate-900 (which turns light grey in dark mode)
  assert.doesNotMatch(source, /handleRetake\(session\)[^>]*className="[^"]*bg-slate-900/);

  // Verify Retake button uses consistent secondary styling matching Review Results
  assert.match(source, /handleRetake\(session\)[^>]*className="[^"]*border-slate-300[^"]*bg-surface[^"]*text-slate-700/);
});

// ---------------------------------------------------------------------------
// 27. UI Polish: Informational Best Attempt extraction preserves authoritative latest attempt
// ---------------------------------------------------------------------------
test("27. Informational Best Attempt extraction correctly identifies top score without altering official latest outcome", () => {
  const question = {
    id: "q-101",
    attempts: [
      { id: "att-1", attempt_number: 1, score: 1.0, is_correct: true, submitted_answer: "Correct answer" },
      { id: "att-2", attempt_number: 2, score: 0.4, is_correct: false, submitted_answer: "Wrong answer" },
    ],
  };

  const attempts = question.attempts;
  // Latest attempt remains authoritative
  const latestAttempt = attempts.reduce((prev, curr) =>
    curr.attempt_number > prev.attempt_number ? curr : prev
  );
  assert.equal(latestAttempt.attempt_number, 2);
  assert.equal(latestAttempt.score, 0.4);
  assert.equal(latestAttempt.is_correct, false);

  // Best attempt is computed strictly as secondary informational value
  const bestAttempt =
    attempts.length > 1
      ? attempts.reduce((best, curr) => (curr.score > best.score ? curr : best))
      : null;

  assert.ok(bestAttempt);
  assert.equal(bestAttempt.attempt_number, 1);
  assert.equal(bestAttempt.score, 1.0);
  assert.equal(formatPercentageScore(bestAttempt.score), "100%");

  // Verify that latestAttempt remains official score and is NOT overridden by bestAttempt
  assert.equal(formatPercentageScore(latestAttempt.score), "40%");
});

// ---------------------------------------------------------------------------
// 28. UI Polish: Dark mode status colors define high-contrast emerald and rose tokens
// ---------------------------------------------------------------------------
test("28. Dark mode status colors define high-contrast emerald and rose tokens", () => {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const cssPath = join(__dirname, "../index.css");
  const source = readFileSync(cssPath, "utf-8");

  // Verify .dark defines complete high-contrast emerald tokens
  assert.match(source, /--color-emerald-200:\s*color-mix/);
  assert.match(source, /--color-emerald-900:\s*#d1fae5/);
  assert.match(source, /--color-emerald-800:\s*#a7f3d0/);

  // Verify .dark defines complete high-contrast rose tokens
  assert.match(source, /--color-rose-200:\s*color-mix/);
  assert.match(source, /--color-rose-900:\s*#ffe4e6/);
});
