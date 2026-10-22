import { ROUTES, routeHref } from "../router/useHashRoute.js";
import { extractLearningPulseKPIs } from "../utils/homePulse.js";

/**
 * LearningPulseRibbon component.
 *
 * Displays a 4-card compact, responsive KPI ribbon highlighting core learning metrics:
 * 1. Questions Attempted
 * 2. Overdue Reviews
 * 3. Attempt Accuracy
 * 4. Completed Revision Sessions
 *
 * Includes loading skeleton, error boundary with retry action, and a deep-link to Progress analytics.
 *
 * @param {Object} props
 * @param {Object|null} props.summary - ProgressSummaryResponse
 * @param {Array<Object>|null} props.schedules - Spaced repetition schedules list
 * @param {boolean} [props.loading=false] - Whether data is loading
 * @param {string|null} [props.error=null] - Error message if fetch failed
 * @param {Function} [props.onRetry] - Callback to retry loading data
 */
export default function LearningPulseRibbon({
  summary = null,
  schedules = null,
  loading = false,
  error = null,
  onRetry = null,
}) {
  const kpis = extractLearningPulseKPIs(summary, schedules);

  return (
    <section aria-label="Learning Pulse" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">
          Learning pulse
        </h2>
        <a
          href={routeHref(ROUTES.PROGRESS)}
          className="text-xs font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          View full analytics →
        </a>
      </div>

      {error ? (
        <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
          <span>{error}</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
            >
              Retry
            </button>
          )}
        </div>
      ) : loading ? (
        <div
          data-testid="learning-pulse-skeleton"
          className="grid grid-cols-2 gap-3.5 lg:grid-cols-4"
        >
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs space-y-2.5"
            >
              <div className="h-5 w-5 rounded bg-slate-200" />
              <div className="h-7 w-16 rounded bg-slate-200" />
              <div className="h-3.5 w-24 rounded bg-slate-200" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
          {/* Card 1: Questions Attempted */}
          <div
            data-testid="kpi-questions-attempted"
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs transition-all hover:border-slate-300"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  {kpis.questionsAttempted.label}
                </span>
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-50 text-xs text-blue-700 border border-blue-200">
                  🎯
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
                {kpis.questionsAttempted.value}
              </p>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-400" title={kpis.questionsAttempted.description}>
              {kpis.questionsAttempted.description}
            </p>
          </div>

          {/* Card 2: Overdue Reviews */}
          <div
            data-testid="kpi-overdue-reviews"
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs transition-all hover:border-slate-300"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  {kpis.overdueReviews.label}
                </span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-md text-xs border ${
                    kpis.overdueReviews.raw && kpis.overdueReviews.raw > 0
                      ? "bg-amber-50 text-amber-700 border-amber-200"
                      : "bg-emerald-50 text-emerald-700 border-emerald-200"
                  }`}
                >
                  ⏰
                </span>
              </div>
              <p
                className={`mt-2 text-2xl font-bold tracking-tight ${
                  kpis.overdueReviews.raw && kpis.overdueReviews.raw > 0
                    ? "text-amber-700"
                    : "text-slate-900"
                }`}
              >
                {kpis.overdueReviews.value}
              </p>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-400" title={kpis.overdueReviews.description}>
              {kpis.overdueReviews.description}
            </p>
          </div>

          {/* Card 3: Attempt Accuracy */}
          <div
            data-testid="kpi-attempt-accuracy"
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs transition-all hover:border-slate-300"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  {kpis.attemptAccuracy.label}
                </span>
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-purple-50 text-xs text-purple-700 border border-purple-200">
                  📊
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
                {kpis.attemptAccuracy.value}
              </p>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-400" title={kpis.attemptAccuracy.description}>
              {kpis.attemptAccuracy.description}
            </p>
          </div>

          {/* Card 4: Completed Sessions */}
          <div
            data-testid="kpi-completed-sessions"
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs transition-all hover:border-slate-300"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  {kpis.completedSessions.label}
                </span>
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-50 text-xs text-emerald-700 border border-emerald-200">
                  ✅
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
                {kpis.completedSessions.value}
              </p>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-400" title={kpis.completedSessions.description}>
              {kpis.completedSessions.description}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
