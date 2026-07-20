import { useState } from "react";
import { generateQuiz } from "../api/quiz";

function QuizPanel({ documentId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [questions, setQuestions] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedAnswers, setSelectedAnswers] = useState({}); // questionId -> optionIndex
  const [submitted, setSubmitted] = useState(false);

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

  const isLoading = status === "loading";
  const answeredCount = Object.keys(selectedAnswers).length;
  const score = questions.reduce(
    (total, question) =>
      total + (selectedAnswers[question.id] === question.correct_answer_index ? 1 : 0),
    0
  );

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Quiz</h2>
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

      {status === "idle" && questions.length === 0 && (
        <p className="text-sm text-slate-500">
          Generate a multiple-choice quiz to check your understanding.
        </p>
      )}

      {status === "error" && <p className="text-sm text-red-600">{errorMessage}</p>}

      {questions.map((question, questionIndex) => (
        <div key={question.id} className="space-y-2">
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
