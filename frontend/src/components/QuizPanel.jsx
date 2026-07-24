import { useState } from "react";
import { generateQuiz } from "../api/quiz";
import { downloadTextFile } from "../utils/downloadFile";
import { quizToMarkdown } from "../utils/markdownExport";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40";

function quizToText(questions) {
  return questions
    .map((question, index) => {
      const optionLines = question.options
        .map((option, optionIndex) => `   ${String.fromCharCode(65 + optionIndex)}. ${option}`)
        .join("\n");
      const correctLetter = String.fromCharCode(65 + question.correct_answer_index);
      return `${index + 1}. ${question.question}\n${optionLines}\nCorrect answer: ${correctLetter}`;
    })
    .join("\n\n");
}

function QuizPanel({ documentId, initialQuestions = [] }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [questions, setQuestions] = useState(initialQuestions);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedAnswers, setSelectedAnswers] = useState({}); // questionId -> optionIndex
  const [submitted, setSubmitted] = useState(false);
  const [copyState, setCopyState] = useState("idle"); // idle | copied
  const [downloadState, setDownloadState] = useState("idle"); // idle | downloaded

  async function handleGenerate() {
    setStatus("loading");
    setErrorMessage("");
    setSubmitted(false);
    setSelectedAnswers({});
    try {
      const result = await generateQuiz(documentId);
      setQuestions(result);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error.message);
    }
  }

  function selectAnswer(questionId, optionIndex) {
    if (submitted) return;
    setSelectedAnswers((previous) => ({ ...previous, [questionId]: optionIndex }));
  }

  async function handleCopy() {
    if (questions.length === 0) return;
    try {
      await navigator.clipboard.writeText(quizToText(questions));
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      // Clipboard access can fail (permissions, insecure context); no
      // crash, just stays in its normal state.
    }
  }

  function handleDownload() {
    if (questions.length === 0) return;
    downloadTextFile("quiz.md", quizToMarkdown(questions));
    setDownloadState("downloaded");
    setTimeout(() => setDownloadState("idle"), 2000);
  }

  const isLoading = status === "loading";
  const answeredCount = Object.keys(selectedAnswers).length;
  const score = questions.reduce(
    (total, question) =>
      total + (selectedAnswers[question.id] === question.correct_answer_index ? 1 : 0),
    0
  );

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Quiz</h2>
        <div className="flex flex-wrap items-center gap-2">
          {questions.length > 0 && (
            <>
              <button onClick={handleCopy} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
                {copyState === "copied" ? "Copied!" : "Copy"}
              </button>
              <button onClick={handleDownload} disabled={isLoading} className={SECONDARY_BUTTON_CLASSES}>
                {downloadState === "downloaded" ? "Downloaded!" : "Download"}
              </button>
            </>
          )}
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:opacity-40"
          >
            {isLoading && (
              <span
                className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
                aria-hidden="true"
              />
            )}
            {isLoading ? "Generating..." : "Generate quiz"}
          </button>
        </div>
      </div>

      {status === "idle" && questions.length === 0 && (
        <p className="text-sm text-slate-500">
          Generate a multiple-choice quiz to check your understanding.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {questions.map((question, questionIndex) => (
        <div key={question.id} className="max-w-3xl space-y-2">
          <p className="text-sm font-medium text-slate-800">
            {questionIndex + 1}. {question.question}
          </p>
          <div className="space-y-1.5">
            {question.options.map((option, optionIndex) => {
              const isSelected = selectedAnswers[question.id] === optionIndex;
              const isCorrect = optionIndex === question.correct_answer_index;

              let stateClasses = "border-slate-200";
              let marker = null;
              if (submitted && isCorrect) {
                stateClasses = "border-emerald-400 bg-emerald-50";
                marker = <span className="font-medium text-emerald-700">&#10003; Correct</span>;
              } else if (submitted && isSelected && !isCorrect) {
                stateClasses = "border-red-400 bg-red-50";
                marker = <span className="font-medium text-red-700">&#10007; Your answer</span>;
              } else if (isSelected) {
                stateClasses = "border-accent-500 bg-accent-50";
              }

              return (
                <button
                  key={optionIndex}
                  type="button"
                  onClick={() => selectAnswer(question.id, optionIndex)}
                  disabled={isLoading}
                  className={`flex w-full items-center justify-between gap-3 rounded-md border px-3 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${stateClasses}`}
                >
                  <span>{option}</span>
                  {marker && <span className="text-xs whitespace-nowrap">{marker}</span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {questions.length > 0 && !submitted && (
        <button
          onClick={() => setSubmitted(true)}
          disabled={answeredCount < questions.length || isLoading}
          className="rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:opacity-40"
        >
          Submit answers ({answeredCount}/{questions.length})
        </button>
      )}

      {submitted && (
        <p className="text-sm font-semibold text-slate-900">
          Score: {score}/{questions.length}
        </p>
      )}
    </div>
  );
}

export default QuizPanel;
