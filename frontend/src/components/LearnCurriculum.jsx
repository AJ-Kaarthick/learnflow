import { useState } from "react";
import { formatContributingDocuments } from "../utils/learnState.js";

function LearnCurriculum({
  outline,
  selectedTopicId,
  selectedSubtopicId,
  onSelectTopic,
  onSelectSubtopic,
  disabled = false,
}) {
  const [showObjectives, setShowObjectives] = useState(false);

  if (!outline) return null;

  const topics = outline.topics || [];
  const learningObjectives = outline.learning_objectives || [];
  const contributing = outline.grounding_metadata?.contributing_documents || [];
  const excluded = outline.grounding_metadata?.excluded_documents || [];
  const contributingText = formatContributingDocuments(contributing);

  return (
    <div className="space-y-4">
      {/* Course header */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-700">
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
            <path d="M10.75 16.82A7.462 7.462 0 0 1 15 15.5c.71 0 1.396.098 2.046.282A.75.75 0 0 0 18 15.06v-11a.75.75 0 0 0-.546-.721A9.006 9.006 0 0 0 15 3a8.963 8.963 0 0 0-4.25 1.065V16.82ZM9.25 4.065A8.963 8.963 0 0 0 5 3c-.85 0-1.673.118-2.454.339A.75.75 0 0 0 2 4.06v11a.75.75 0 0 0 .954.721A7.506 7.506 0 0 1 5 15.5c1.579 0 3.042.487 4.25 1.32V4.065Z" />
          </svg>
          Study Curriculum
        </div>
        <h3 className="mt-1 text-base font-semibold text-slate-900">{outline.title}</h3>
        {outline.description && (
          <p className="mt-1 text-xs leading-relaxed text-slate-600">{outline.description}</p>
        )}

        {/* Contributing documents badge */}
        {contributingText && (
          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="font-medium text-slate-700">Sources:</span>
            <span className="truncate" title={contributingText}>
              {contributingText}
            </span>
          </div>
        )}

        {/* Excluded documents advisory if backend excluded any */}
        {excluded.length > 0 && (
          <div className="mt-2 rounded bg-amber-50 p-2 text-[11px] text-amber-800">
            <span className="font-semibold">Excluded: </span>
            {excluded.map((d) => d.original_filename).join(", ")} (unreadable/unready)
          </div>
        )}

        {/* Course learning objectives toggle */}
        {learningObjectives.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-2">
            <button
              type="button"
              onClick={() => setShowObjectives((prev) => !prev)}
              aria-expanded={showObjectives}
              className="flex w-full items-center justify-between text-left text-xs font-medium text-slate-600 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 rounded"
            >
              <span>Course Objectives ({learningObjectives.length})</span>
              <span className="text-[10px] text-slate-400">{showObjectives ? "Hide" : "Show"}</span>
            </button>
            {showObjectives && (
              <ul className="mt-2 space-y-1 pl-4 text-xs text-slate-600 list-disc">
                {learningObjectives.map((obj, i) => (
                  <li key={i}>{obj}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Topics list */}
      <nav aria-label="Curriculum topics" className="space-y-1.5">
        <span className="px-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Topics ({topics.length})
        </span>

        {topics.map((topic, index) => {
          const isTopicActive = selectedTopicId === topic.id;
          const subtopics = topic.subtopics || [];

          return (
            <div
              key={topic.id}
              className={`rounded-lg border transition-all ${
                isTopicActive
                  ? "border-accent-300 bg-accent-50/70 shadow-xs"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/60"
              }`}
            >
              <button
                type="button"
                disabled={disabled}
                onClick={() => onSelectTopic?.(topic)}
                aria-current={isTopicActive ? "true" : undefined}
                className="flex w-full items-start gap-2.5 p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 rounded-lg disabled:cursor-not-allowed"
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
                    isTopicActive ? "bg-accent-600 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-xs font-semibold leading-snug ${
                      isTopicActive ? "text-accent-900" : "text-slate-800"
                    }`}
                  >
                    {topic.title}
                  </p>
                  {topic.description && (
                    <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-slate-500">
                      {topic.description}
                    </p>
                  )}
                </div>
              </button>

              {/* Subtopics under active topic */}
              {isTopicActive && subtopics.length > 0 && (
                <div className="border-t border-accent-200/60 px-3 py-2 space-y-1 bg-accent-50/40">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-accent-700">
                    Subtopics:
                  </span>
                  <div className="space-y-1">
                    {subtopics.map((subtopic) => {
                      const isSubActive = selectedSubtopicId === subtopic.id;
                      return (
                        <button
                          key={subtopic.id}
                          type="button"
                          disabled={disabled}
                          onClick={() => onSelectSubtopic?.(topic, subtopic)}
                          className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs font-medium transition-colors ${
                            isSubActive
                              ? "bg-accent-200 text-accent-900 font-semibold"
                              : "text-slate-700 hover:bg-accent-100"
                          }`}
                        >
                          <span className="text-accent-500">&bull;</span>
                          <span className="truncate">{subtopic.title}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

export default LearnCurriculum;
