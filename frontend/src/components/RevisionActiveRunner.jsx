import { useState } from "react";
import { completeRevisionSession, submitRevisionAttempt } from "../api/revision.js";
import { isGuestLimitError } from "../api/errors.js";
import GuestLimitNotice from "./GuestLimitNotice.jsx";
import {
  advanceToNextQuestion,
  applySessionCompletion,
  calculateSessionProgress,
  canSubmitAnswer,
  createInitialRunnerState,
  formatPercentageScore,
  getCurrentQuestion,
  getQuestionDocumentTitle,
  goToQuestionIndex,
  isAtLastQuestion,
  isDocumentArchived,
  recordAttemptInState,
  updateAnswerInState,
} from "../utils/revisionState.js";

function RevisionActiveRunner({ session, onExit, onReview }) {
  const [runnerState, setRunnerState] = useState(() => createInitialRunnerState(session));
  const [showEvidence, setShowEvidence] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  const currentQuestion = getCurrentQuestion(runnerState);
  const currentAnswer = currentQuestion ? runnerState.answers[currentQuestion.id] || "" : "";
  const latestAttempt = currentQuestion ? runnerState.latestAttempts[currentQuestion.id] : null;
  const attemptsHistory = currentQuestion ? runnerState.attemptsHistory[currentQuestion.id] || [] : [];
  const progress = calculateSessionProgress(runnerState);
  const isFinal = isAtLastQuestion(runnerState);

  async function handleSubmitAnswer(e) {
    e.preventDefault();
    if (!currentQuestion || !canSubmitAnswer(currentQuestion, currentAnswer, runnerState.isSubmitting)) {
      return;
    }

    setRunnerState((prev) => ({ ...prev, isSubmitting: true, submissionError: null }));
    setIsRetrying(false);

    try {
      const attempt = await submitRevisionAttempt(
        runnerState.session.id,
        currentQuestion.id,
        currentAnswer
      );
      setRunnerState((prev) => recordAttemptInState(prev, currentQuestion.id, attempt));
    } catch (error) {
      setRunnerState((prev) => ({
        ...prev,
        isSubmitting: false,
        submissionError: error,
      }));
    }
  }

  async function handleCompleteSession() {
    setRunnerState((prev) => ({ ...prev, isCompleting: true, completionError: null }));

    try {
      const updatedSession = await completeRevisionSession(runnerState.session.id);
      setRunnerState((prev) => applySessionCompletion(prev, updatedSession));
    } catch (error) {
      setRunnerState((prev) => ({
        ...prev,
        isCompleting: false,
        completionError: error,
      }));
    }
  }

  function handleNext() {
    setShowEvidence(false);
    setIsRetrying(false);
    setRunnerState((prev) => advanceToNextQuestion(prev));
  }

  function handleSelectOption(option) {
    if (runnerState.isSubmitting) return;
    setRunnerState((prev) => updateAnswerInState(prev, currentQuestion.id, option));
  }

  function handleAnswerChange(val) {
    if (runnerState.isSubmitting) return;
    setRunnerState((prev) => updateAnswerInState(prev, currentQuestion.id, val));
  }

  function handleRetryQuestion() {
    setIsRetrying(true);
    // Keep attempt history, but allow user to submit again
  }

  // Completed State View (Minimal for Phase 3)
  if (runnerState.isCompleted) {
    return (
      <div className="mx-auto max-w-3xl p-4 sm:p-6 lg:p-8">
        <div className="rounded-2xl border border-emerald-200 bg-surface p-8 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-8 w-8" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Revision Session Complete!
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            You finished all questions in this session.
          </p>

          <div className="mt-8 grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-6 sm:grid-cols-3">
            <div>
              <p className="text-xs font-medium text-slate-500">Final Score</p>
              <p className="mt-1 text-2xl font-bold text-accent-700">
                {formatPercentageScore(runnerState.finalScore)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Questions Completed</p>
              <p className="mt-1 text-2xl font-bold text-slate-800">
                {progress.answered} / {progress.total}
              </p>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <p className="text-xs font-medium text-slate-500">Status</p>
              <span className="mt-2 inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                Completed
              </span>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {onReview && (
              <button
                type="button"
                onClick={() => onReview(runnerState.session)}
                className="rounded-lg border border-slate-300 bg-surface px-6 py-2.5 text-sm font-semibold text-slate-700 shadow-xs transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Review Full Results
              </button>
            )}
            <button
              type="button"
              onClick={onExit}
              className="rounded-lg bg-accent-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              Start New Revision Session
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="mx-auto max-w-3xl p-8 text-center">
        <p className="text-sm text-slate-500">No questions found in this revision session.</p>
        <button
          type="button"
          onClick={onExit}
          className="mt-4 rounded-md bg-accent-600 px-4 py-2 text-xs font-medium text-white"
        >
          Back to Setup
        </button>
      </div>
    );
  }

  const isMCQ = currentQuestion.question_type === "multiple_choice";
  const hasEvaluated = Boolean(latestAttempt) && !isRetrying;
  const isCorrect = latestAttempt ? (latestAttempt.is_correct ?? (latestAttempt.score >= 0.7)) : false;

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6 lg:p-8">
      {/* Session Top Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-accent-100 px-2 py-0.5 text-xs font-medium text-accent-700">
              Revision Active Runner
            </span>
            {runnerState.session.config?.difficulty && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 capitalize">
                {runnerState.session.config.difficulty}
              </span>
            )}
            {runnerState.session.config?.mode && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 capitalize">
                {runnerState.session.config.mode}
              </span>
            )}
          </div>
          <h1 className="mt-1 text-lg font-bold text-slate-900 sm:text-xl">
            {runnerState.session.title || "Revision Session"}
          </h1>
        </div>

        <button
          type="button"
          onClick={onExit}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          Exit Session
        </button>
      </div>

      {/* Progress & Question Navigation Pills */}
      <div className="mb-6 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            Question <span className="font-semibold text-slate-900">{runnerState.currentIndex + 1}</span> of{" "}
            {runnerState.questions.length}
          </span>
          <span>
            {progress.answered} answered ({progress.percentage}%)
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full bg-accent-600 transition-all duration-300"
            style={{ width: `${progress.percentage}%` }}
          />
        </div>

        {/* Question jumper tabs */}
        <div className="flex flex-wrap gap-1.5 pt-2">
          {runnerState.questions.map((q, idx) => {
            const isCurrent = idx === runnerState.currentIndex;
            const isAnswered = Boolean(runnerState.latestAttempts[q.id]);
            return (
              <button
                key={q.id}
                type="button"
                onClick={() => {
                  setShowEvidence(false);
                  setIsRetrying(false);
                  setRunnerState((prev) => goToQuestionIndex(prev, idx));
                }}
                aria-label={`Jump to question ${idx + 1}`}
                className={`flex h-7 w-7 items-center justify-center rounded-md text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                  isCurrent
                    ? "bg-accent-600 text-white"
                    : isAnswered
                      ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {idx + 1}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Question Card */}
      <div className="rounded-xl border border-slate-200 bg-surface p-6 shadow-xs">
        {/* Question Type & Source Meta */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                isMCQ
                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                  : "bg-purple-50 text-purple-700 border border-purple-200"
              }`}
            >
              {isMCQ ? "Multiple Choice" : "Open Ended"}
            </span>

            {attemptsHistory.length > 0 && (
              <span className="text-xs text-slate-400">
                Attempt #{attemptsHistory.length}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span>Source:</span>
            <span
              className={`font-medium truncate max-w-[220px] ${
                isDocumentArchived(currentQuestion) ? "text-amber-700" : "text-slate-700"
              }`}
              title={getQuestionDocumentTitle(currentQuestion)}
            >
              {getQuestionDocumentTitle(currentQuestion)}
            </span>
            {isDocumentArchived(currentQuestion) && (
              <span className="rounded bg-amber-100 px-1.5 py-0.2 text-[10px] text-amber-800">
                Archived
              </span>
            )}
          </div>
        </div>

        {/* Question Text */}
        <div className="mt-4">
          <h2 className="text-base font-semibold leading-relaxed text-slate-900 sm:text-lg">
            {currentQuestion.question_text}
          </h2>
        </div>

        {/* Grounding Evidence / Citation preview toggle */}
        {currentQuestion.evidence_snippet && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setShowEvidence((prev) => !prev)}
              className="inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:text-accent-700 focus-visible:outline-none focus-visible:underline"
            >
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className={`h-3.5 w-3.5 transition-transform ${showEvidence ? "rotate-90" : ""}`}
              >
                <path
                  fillRule="evenodd"
                  d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                  clipRule="evenodd"
                />
              </svg>
              {showEvidence ? "Hide source evidence" : "Show source evidence snippet"}
            </button>
            {showEvidence && (
              <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 leading-relaxed italic">
                &quot;{currentQuestion.evidence_snippet}&quot;
              </div>
            )}
          </div>
        )}

        {/* Error Messages */}
        {runnerState.submissionError && (
          <div className="mt-4">
            {isGuestLimitError(runnerState.submissionError) ? (
              <GuestLimitNotice error={runnerState.submissionError} />
            ) : (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {runnerState.submissionError.message || "Failed to submit attempt. Please try again."}
              </div>
            )}
          </div>
        )}

        {/* Answer Controls: MCQ vs Open-Ended */}
        <form onSubmit={handleSubmitAnswer} className="mt-6">
          {isMCQ ? (
            <div className="space-y-2.5" role="radiogroup" aria-label="Multiple choice options">
              {(currentQuestion.options || []).map((option, idx) => {
                const isSelected = currentAnswer === option;
                const optionLetter = String.fromCharCode(65 + idx);

                return (
                  <label
                    key={idx}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors focus-within:ring-2 focus-within:ring-accent-500 ${
                      isSelected
                        ? "border-accent-600 bg-accent-50/60 ring-1 ring-accent-600"
                        : "border-slate-200 bg-surface hover:border-slate-300 hover:bg-slate-50/50"
                    } ${runnerState.isSubmitting ? "pointer-events-none opacity-60" : ""}`}
                  >
                    <input
                      type="radio"
                      name={`question-${currentQuestion.id}`}
                      value={option}
                      checked={isSelected}
                      onChange={() => handleSelectOption(option)}
                      disabled={runnerState.isSubmitting}
                      className="mt-0.5 h-4 w-4 shrink-0 text-accent-600 focus:ring-accent-500"
                    />
                    <div className="min-w-0 flex-1 leading-normal text-slate-900">
                      <span className="mr-2 font-bold text-slate-500">{optionLetter}.</span>
                      {option}
                    </div>
                  </label>
                );
              })}
            </div>
          ) : (
            <div>
              <label htmlFor="open-ended-answer" className="block text-xs font-medium text-slate-700">
                Your Answer / Explanation
              </label>
              <textarea
                id="open-ended-answer"
                rows={4}
                value={currentAnswer}
                onChange={(e) => handleAnswerChange(e.target.value)}
                disabled={runnerState.isSubmitting}
                placeholder="Explain in your own words based on the source documents..."
                className="mt-1.5 block w-full rounded-lg border border-slate-300 bg-surface p-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500 disabled:opacity-60"
              />
            </div>
          )}

          {/* Submission Button (if not yet evaluated, or currently retrying) */}
          {(!hasEvaluated || isRetrying) && (
            <div className="mt-5 flex justify-end">
              <button
                type="submit"
                disabled={!canSubmitAnswer(currentQuestion, currentAnswer, runnerState.isSubmitting)}
                className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-5 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {runnerState.isSubmitting ? (
                  <>
                    <svg
                      className="h-3.5 w-3.5 animate-spin text-white"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    <span>Evaluating Answer...</span>
                  </>
                ) : (
                  <span>Submit Answer</span>
                )}
              </button>
            </div>
          )}
        </form>

        {/* Evaluation Result Card (Displayed after successful attempt) */}
        {hasEvaluated && latestAttempt && (
          <div className="mt-6 space-y-4 border-t border-slate-100 pt-5">
            {/* Result Header Banner */}
            <div
              className={`flex items-center justify-between rounded-lg border p-4 ${
                isCorrect
                  ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : "border-amber-200 bg-amber-50 text-amber-900"
              }`}
            >
              <div className="flex items-center gap-2.5">
                {isCorrect ? (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-600 text-white text-xs">
                    &#10003;
                  </span>
                ) : (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-600 text-white text-xs">
                    !
                  </span>
                )}
                <div>
                  <p className="text-sm font-bold">
                    {isCorrect ? "Correct!" : "Needs Improvement"}
                  </p>
                  <p className="text-xs text-slate-600">
                    Attempt #{latestAttempt.attempt_number}
                  </p>
                </div>
              </div>
              <span className="rounded-md bg-white/80 px-2.5 py-1 text-xs font-bold shadow-2xs">
                Score: {formatPercentageScore(latestAttempt.score)}
              </span>
            </div>

            {/* Evaluator Feedback */}
            {latestAttempt.feedback && (
              <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Feedback
                </p>
                <p className="mt-1 text-sm text-slate-800 leading-relaxed">
                  {latestAttempt.feedback}
                </p>
              </div>
            )}

            {/* Correct/Reference Answer */}
            {(latestAttempt.correct_answer || currentQuestion.correct_answer) && (
              <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Correct / Model Answer
                </p>
                <p className="mt-1 text-sm font-medium text-slate-900">
                  {latestAttempt.correct_answer || currentQuestion.correct_answer}
                </p>
              </div>
            )}

            {/* Question Explanation */}
            {(latestAttempt.explanation || currentQuestion.explanation) && (
              <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Explanation
                </p>
                <p className="mt-1 text-sm text-slate-700 leading-relaxed">
                  {latestAttempt.explanation || currentQuestion.explanation}
                </p>
              </div>
            )}

            {/* Post-Evaluation Actions: Retry / Next / Complete */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={handleRetryQuestion}
                className="rounded-md border border-slate-300 bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Try Again (New Attempt)
              </button>

              <div className="flex items-center gap-2">
                {!isFinal ? (
                  <button
                    type="button"
                    onClick={handleNext}
                    className="inline-flex items-center gap-1.5 rounded-md bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                  >
                    <span>Next Question</span>
                    <svg viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                      <path
                        fillRule="evenodd"
                        d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCompleteSession}
                    disabled={runnerState.isCompleting}
                    className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-50"
                  >
                    {runnerState.isCompleting ? (
                      <>
                        <svg
                          className="h-3.5 w-3.5 animate-spin text-white"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          />
                        </svg>
                        <span>Finalizing Session...</span>
                      </>
                    ) : (
                      <span>Complete Session</span>
                    )}
                  </button>
                )}
              </div>
            </div>

            {runnerState.completionError && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {runnerState.completionError.message || "Failed to complete session."}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default RevisionActiveRunner;
