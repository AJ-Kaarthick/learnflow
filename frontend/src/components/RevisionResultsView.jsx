import { useState } from "react";
import {
  formatDate,
  formatPercentageScore,
  getQuestionDocumentTitle,
  isDocumentArchived,
} from "../utils/revisionState.js";

function RevisionResultsView({ session, onBackToHistory, onRetake }) {
  const [expandedSnippets, setExpandedSnippets] = useState({});
  const [expandedHistories, setExpandedHistories] = useState({});

  if (!session) {
    return (
      <div className="mx-auto max-w-3xl p-8 text-center">
        <p className="text-sm text-slate-500">No session details available.</p>
        <button
          type="button"
          onClick={onBackToHistory}
          className="mt-4 rounded-md bg-accent-600 px-4 py-2 text-xs font-semibold text-white"
        >
          Back to History
        </button>
      </div>
    );
  }

  const questions = Array.isArray(session.questions) ? session.questions : [];
  const documents = Array.isArray(session.documents) ? session.documents : [];

  function toggleSnippet(questionId) {
    setExpandedSnippets((prev) => ({ ...prev, [questionId]: !prev[questionId] }));
  }

  function toggleHistory(questionId) {
    setExpandedHistories((prev) => ({ ...prev, [questionId]: !prev[questionId] }));
  }

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6 lg:p-8">
      {/* Header Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
              Completed Session Review
            </span>
            {session.completed_at && (
              <span className="text-xs text-slate-400">
                Completed on {formatDate(session.completed_at)}
              </span>
            )}
          </div>
          <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            {session.title || "Revision Session"}
          </h1>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={onBackToHistory}
            className="rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
          >
            ← Back to History
          </button>
          <button
            type="button"
            onClick={() => onRetake(session)}
            className="rounded-lg bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
          >
            Retake Session
          </button>
        </div>
      </div>

      {/* Summary Metrics Banner */}
      <div className="mb-8 grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-surface p-5 shadow-xs sm:grid-cols-4">
        <div>
          <p className="text-xs font-medium text-slate-500">Official Final Score</p>
          <p className="mt-1 text-2xl font-bold text-accent-700">
            {formatPercentageScore(session.score)}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">Questions Completed</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">
            {session.total_questions}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">Difficulty Level</p>
          <p className="mt-1 text-base font-semibold text-slate-700 capitalize">
            {session.config?.difficulty || "Standard"}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">Session Mode</p>
          <p className="mt-1 text-base font-semibold text-slate-700 capitalize">
            {session.config?.mode || "Practice"}
          </p>
        </div>
      </div>

      {/* Bound Source Documents */}
      {documents.length > 0 && (
        <div className="mb-8 rounded-xl border border-slate-200 bg-surface p-5 shadow-xs">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Contributing Documents ({documents.length})
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {documents.map((doc, idx) => {
              const isArchived = doc.status === "archived" || doc.original_filename === "Archived Document";
              return (
                <span
                  key={doc.document_id || idx}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                    isArchived
                      ? "border border-amber-200 bg-amber-50 text-amber-800"
                      : "border border-slate-200 bg-slate-50 text-slate-700"
                  }`}
                >
                  <span className="truncate max-w-[220px]">
                    {doc.original_filename || "Archived Document"}
                  </span>
                  {isArchived && (
                    <span className="text-[10px] text-amber-600 font-semibold">(Archived)</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Question-by-Question Review */}
      <div className="space-y-6">
        <h2 className="text-base font-semibold text-slate-900">
          Question Results &amp; Feedback
        </h2>

        {questions.map((question, qIdx) => {
          const attempts = Array.isArray(question.attempts) ? question.attempts : [];
          const latestAttempt =
            attempts.length > 0
              ? attempts.reduce((prev, curr) =>
                  curr.attempt_number > prev.attempt_number ? curr : prev
                )
              : null;

          const isMCQ = question.question_type === "multiple_choice";
          const isArchived = isDocumentArchived(question);
          const docTitle = getQuestionDocumentTitle(question);
          const isSnippetOpen = Boolean(expandedSnippets[question.id]);
          const isHistoryOpen = Boolean(expandedHistories[question.id]);

          const isCorrect = latestAttempt
            ? (latestAttempt.is_correct ?? (latestAttempt.score >= 0.7))
            : false;

          return (
            <div
              key={question.id}
              className="rounded-xl border border-slate-200 bg-surface p-6 shadow-xs space-y-4"
            >
              {/* Question Meta Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 text-sm">
                    Question {question.position || qIdx + 1}
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      isMCQ
                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                        : "bg-purple-50 text-purple-700 border border-purple-200"
                    }`}
                  >
                    {isMCQ ? "Multiple Choice" : "Open Ended"}
                  </span>
                  {attempts.length > 0 && (
                    <span className="text-xs text-slate-400">
                      {attempts.length} {attempts.length === 1 ? "attempt" : "attempts"}
                    </span>
                  )}
                </div>

                {/* Source Provenance */}
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <span>Source:</span>
                  <span
                    className={`font-medium ${isArchived ? "text-amber-700" : "text-slate-800"}`}
                    title={docTitle}
                  >
                    {docTitle}
                  </span>
                  {isArchived && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.2 text-[10px] text-amber-800">
                      Archived
                    </span>
                  )}
                </div>
              </div>

              {/* Question Text */}
              <p className="text-base font-medium text-slate-900 leading-relaxed">
                {question.question_text}
              </p>

              {/* Source Evidence Snippet Toggle */}
              {question.evidence_snippet && (
                <div>
                  <button
                    type="button"
                    onClick={() => toggleSnippet(question.id)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:text-accent-700 focus-visible:outline-none focus-visible:underline"
                  >
                    <svg
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className={`h-3.5 w-3.5 transition-transform ${isSnippetOpen ? "rotate-90" : ""}`}
                    >
                      <path
                        fillRule="evenodd"
                        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {isSnippetOpen ? "Hide source evidence" : "Show source evidence snippet"}
                  </button>
                  {isSnippetOpen && (
                    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 italic leading-relaxed">
                      &quot;{question.evidence_snippet}&quot;
                    </div>
                  )}
                </div>
              )}

              {/* Options for MCQ */}
              {isMCQ && Array.isArray(question.options) && (
                <div className="space-y-1.5 pt-1">
                  {question.options.map((option, optIdx) => {
                    const isLearnerAnswer = latestAttempt?.submitted_answer === option;
                    const isModelAnswer =
                      (latestAttempt?.correct_answer || question.correct_answer) === option;
                    const optLetter = String.fromCharCode(65 + optIdx);

                    let optClasses = "border-slate-200 bg-surface text-slate-700";
                    let badge = null;

                    if (isModelAnswer) {
                      optClasses = "border-emerald-300 bg-emerald-50 text-emerald-900 font-medium";
                      badge = <span className="text-xs font-semibold text-emerald-700">&#10003; Correct Answer</span>;
                    } else if (isLearnerAnswer && !isModelAnswer) {
                      optClasses = "border-rose-300 bg-rose-50 text-rose-900 font-medium";
                      badge = <span className="text-xs font-semibold text-rose-700">&#10007; Your Answer</span>;
                    }

                    return (
                      <div
                        key={optIdx}
                        className={`flex items-center justify-between gap-3 rounded-lg border p-2.5 text-xs sm:text-sm ${optClasses}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-400">{optLetter}.</span>
                          <span>{option}</span>
                        </div>
                        {badge}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Latest Attempt Outcome Banner */}
              {latestAttempt ? (
                <div
                  className={`rounded-lg border p-4 ${
                    isCorrect
                      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                      : "border-amber-200 bg-amber-50 text-amber-900"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`flex h-5 w-5 items-center justify-center rounded-full text-white text-[11px] font-bold ${
                          isCorrect ? "bg-emerald-600" : "bg-amber-600"
                        }`}
                      >
                        {isCorrect ? "✓" : "!"}
                      </span>
                      <span className="text-xs font-bold uppercase tracking-wider">
                        {isCorrect ? "Correct" : "Needs Improvement"}
                      </span>
                      <span className="text-xs text-slate-500 font-normal">
                        (Latest Attempt #{latestAttempt.attempt_number})
                      </span>
                    </div>
                    <span className="rounded-md bg-white/90 px-2 py-0.5 text-xs font-bold shadow-2xs">
                      Score: {formatPercentageScore(latestAttempt.score)}
                    </span>
                  </div>

                  {/* Open-Ended Learner Answer Display */}
                  {!isMCQ && latestAttempt.submitted_answer && (
                    <div className="mt-3 rounded-md bg-white/80 p-3 text-xs text-slate-800">
                      <p className="font-semibold text-slate-500 text-[11px] uppercase tracking-wider">
                        Your Submitted Response
                      </p>
                      <p className="mt-1 leading-relaxed">{latestAttempt.submitted_answer}</p>
                    </div>
                  )}

                  {/* Evaluator Feedback */}
                  {latestAttempt.feedback && (
                    <div className="mt-3 text-xs leading-relaxed text-slate-800">
                      <strong className="font-semibold text-slate-700">Feedback: </strong>
                      {latestAttempt.feedback}
                    </div>
                  )}

                  {/* Model / Reference Answer */}
                  {(latestAttempt.correct_answer || question.correct_answer) && !isMCQ && (
                    <div className="mt-3 rounded-md bg-emerald-100/60 p-3 text-xs text-emerald-950">
                      <p className="font-semibold text-[11px] uppercase tracking-wider text-emerald-800">
                        Model Answer / Reference
                      </p>
                      <p className="mt-1 leading-relaxed">
                        {latestAttempt.correct_answer || question.correct_answer}
                      </p>
                    </div>
                  )}

                  {/* Explanation */}
                  {(latestAttempt.explanation || question.explanation) && (
                    <div className="mt-3 text-xs leading-relaxed text-slate-700">
                      <strong className="font-semibold text-slate-800">Explanation: </strong>
                      {latestAttempt.explanation || question.explanation}
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500 italic">
                  Not attempted during this session.
                </div>
              )}

              {/* Historical Attempts Accordion (when more than 1 attempt exists) */}
              {attempts.length > 1 && (
                <div className="border-t border-slate-100 pt-3">
                  <button
                    type="button"
                    onClick={() => toggleHistory(question.id)}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 focus-visible:outline-none focus-visible:underline"
                  >
                    <span>Attempt History ({attempts.length} attempts recorded)</span>
                    <span className="text-[10px] text-slate-400">
                      {isHistoryOpen ? "▲ Hide" : "▼ Expand"}
                    </span>
                  </button>

                  {isHistoryOpen && (
                    <div className="mt-3 space-y-2.5">
                      {attempts.map((att) => {
                        const isLatest = att.attempt_number === latestAttempt?.attempt_number;
                        return (
                          <div
                            key={att.id || att.attempt_number}
                            className={`rounded-lg border p-3 text-xs ${
                              isLatest
                                ? "border-accent-200 bg-accent-50/40"
                                : "border-slate-200 bg-slate-50/50"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-700">
                                Attempt #{att.attempt_number}
                                {isLatest && (
                                  <span className="ml-2 rounded-full bg-accent-100 px-2 py-0.5 text-[10px] font-semibold text-accent-700">
                                    Latest (Official)
                                  </span>
                                )}
                              </span>
                              <span className="font-semibold text-slate-600">
                                Score: {formatPercentageScore(att.score)}
                              </span>
                            </div>

                            <p className="mt-1 text-slate-800">
                              <span className="font-medium text-slate-500">Answer: </span>
                              {att.submitted_answer}
                            </p>
                            {att.feedback && (
                              <p className="mt-1 text-slate-600">
                                <span className="font-medium text-slate-500">Feedback: </span>
                                {att.feedback}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default RevisionResultsView;
