import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import LearnActionBar from "./LearnActionBar.jsx";
import LearnCitations from "./LearnCitations.jsx";

function LearnTopicViewer({
  topicTitle,
  parentTopicTitle,
  topicContent,
  activeAction,
  activeDepth,
  onAction,
  onResetAction,
  onDepthChange,
  isLoading = false,
  loadingAction = null,
  disabled = false,
}) {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        {parentTopicTitle && (
          <div className="mb-1 flex items-center gap-1 text-xs text-slate-500">
            <span>{parentTopicTitle}</span>
            <span aria-hidden="true">&rsaquo;</span>
            <span className="font-medium text-slate-700">Subtopic</span>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-bold tracking-tight text-slate-900">{topicTitle}</h2>
          {activeAction && (
            <span className="rounded-full bg-accent-100 px-2.5 py-0.5 text-xs font-semibold text-accent-800 capitalize">
              {activeAction === "elaborate" ? "Deep Dive" : activeAction} Mode
            </span>
          )}
        </div>
      </div>

      {/* Action bar */}
      <LearnActionBar
        activeAction={activeAction}
        activeDepth={activeDepth}
        onAction={onAction}
        onResetAction={onResetAction}
        onDepthChange={onDepthChange}
        disabled={disabled || isLoading}
        loadingAction={loadingAction}
      />

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="space-y-4 py-2" role="status" aria-label="Loading topic explanation">
          <div className="flex items-center gap-2 text-xs font-medium text-accent-700">
            <span
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent"
              aria-hidden="true"
            />
            <span>Generating grounded explanation with source citations...</span>
          </div>
          <div className="space-y-2.5 animate-pulse">
            <div className="h-4 w-3/4 rounded bg-slate-200" />
            <div className="h-4 w-full rounded bg-slate-100" />
            <div className="h-4 w-5/6 rounded bg-slate-100" />
            <div className="h-4 w-2/3 rounded bg-slate-100" />
          </div>
          <div className="mt-6 rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-2 animate-pulse">
            <div className="h-3.5 w-1/4 rounded bg-slate-200" />
            <div className="h-3 w-1/2 rounded bg-slate-100" />
          </div>
        </div>
      ) : topicContent ? (
        <div className="space-y-6">
          {/* Grounded Explanation */}
          <div className="prose prose-sm max-w-none text-slate-800 leading-relaxed break-words">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {topicContent.explanation || ""}
            </ReactMarkdown>
          </div>

          {/* Key Terms */}
          {Array.isArray(topicContent.key_terms) && topicContent.key_terms.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-700">
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-4 w-4 text-accent-600"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 1c3.866 0 7 3.134 7 7 0 2.9-1.583 5.434-3.926 6.467l-.074.033v1.75a.75.75 0 0 1-.75.75H7.75a.75.75 0 0 1-.75-.75v-1.75l-.074-.033A7.002 7.002 0 0 1 3 8c0-3.866 3.134-7 7-7Zm-1.25 16h2.5a.75.75 0 0 1 0 1.5h-2.5a.75.75 0 0 1 0-1.5ZM8.5 7.75a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0Z"
                    clipRule="evenodd"
                  />
                </svg>
                Key Terms ({topicContent.key_terms.length})
              </h4>
              <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {topicContent.key_terms.map((item, index) => (
                  <div
                    key={index}
                    className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5 text-xs"
                  >
                    <dt className="font-semibold text-slate-900">{item.term}</dt>
                    <dd className="mt-1 text-slate-600 leading-relaxed">{item.definition}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Key Takeaways */}
          {Array.isArray(topicContent.key_takeaways) && topicContent.key_takeaways.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-accent-50/30 p-4">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-700">
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-4 w-4 text-emerald-600"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                    clipRule="evenodd"
                  />
                </svg>
                Key Takeaways
              </h4>
              <ul className="mt-2.5 space-y-2 text-xs text-slate-700">
                {topicContent.key_takeaways.map((takeaway, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-emerald-500 font-bold">&check;</span>
                    <span className="leading-relaxed">{takeaway}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Grounded Source Citations */}
          <LearnCitations sources={topicContent.sources || []} />
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-xs text-slate-500">
          Select a topic or click an action above to view the explanation.
        </div>
      )}
    </div>
  );
}

export default LearnTopicViewer;
