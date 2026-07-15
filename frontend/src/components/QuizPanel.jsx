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
    <div className="border-t border-slate-200 pt-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-900">Quiz</h2>
        <button
          onClick={handleGenerate}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
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
          <div className="space-y-1">
            {question.options.map((option, optionIndex) => {
              const isSelected = selectedAnswers[question.id] === optionIndex;
              const isCorrect = optionIndex === question.correct_answer_index;

              let stateClasses = "border-slate-200";
              if (submitted && isCorrect) {
                stateClasses = "border-emerald-400 bg-emerald-50";
              } else if (submitted && isSelected && !isCorrect) {
                stateClasses = "border-red-400 bg-red-50";
              } else if (isSelected) {
                stateClasses = "border-slate-900";
              }

              return (
                <button
                  key={optionIndex}
                  type="button"
                  onClick={() => selectAnswer(question.id, optionIndex)}
                  disabled={isLoading}
                  className={`w-full text-left text-sm rounded-md border px-3 py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${stateClasses}`}
                >
                  {option}
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
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          Submit answers ({answeredCount}/{questions.length})
        </button>
      )}

      {submitted && (
        <p className="text-sm font-medium text-slate-900">
          Score: {score}/{questions.length}
        </p>
      )}
    </div>
  );
}

export default QuizPanel;
