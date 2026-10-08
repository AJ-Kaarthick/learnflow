import { useEffect, useState } from "react";
import { getRevisionSession, listRevisionSessions } from "../api/revision.js";
import {
  formatDate,
  formatPercentageScore,
  getStatusBadgeClasses,
} from "../utils/revisionState.js";

function RevisionHistoryView({
  onStartNewSession,
  onResumeSession,
  onReviewSession,
  onRetakeSession,
}) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busySessionId, setBusySessionId] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchSessions() {
      setLoading(true);
      setError(null);
      try {
        const data = await listRevisionSessions();
        if (!cancelled) {
          setSessions(data || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchSessions();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleResume(summary) {
    setBusySessionId(summary.id);
    try {
      const fullDetail = await getRevisionSession(summary.id);
      onResumeSession(fullDetail);
    } catch (err) {
      setError(err);
    } finally {
      setBusySessionId(null);
    }
  }

  async function handleReview(summary) {
    setBusySessionId(summary.id);
    try {
      const fullDetail = await getRevisionSession(summary.id);
      onReviewSession(fullDetail);
    } catch (err) {
      setError(err);
    } finally {
      setBusySessionId(null);
    }
  }

  async function handleRetake(summary) {
    setBusySessionId(summary.id);
    try {
      const fullDetail = await getRevisionSession(summary.id);
      onRetakeSession(fullDetail);
    } catch (err) {
      setError(err);
    } finally {
      setBusySessionId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <svg
          className="h-8 w-8 animate-spin text-accent-600"
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
        <p className="mt-3 text-xs font-medium text-slate-500">Loading revision history...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
          <p className="font-semibold">Unable to Load Revision History</p>
          <p className="mt-1 text-xs text-red-600">{error.message || String(error)}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 rounded-md bg-red-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-50 text-accent-600">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-7 w-7" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
        </div>
        <h2 className="mt-4 text-base font-semibold text-slate-900">No revision sessions yet</h2>
        <p className="mt-1 text-xs text-slate-500 leading-relaxed">
          Start your first revision session to practice grounded questions, track your attempts, and retain concepts.
        </p>
        <div className="mt-6">
          <button
            type="button"
            onClick={onStartNewSession}
            className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
          >
            Start New Session
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6 lg:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            Revision Session History
          </h1>
          <p className="text-xs text-slate-500">
            View completed results, resume in-progress practice, or retake past sessions.
          </p>
        </div>
        <button
          type="button"
          onClick={onStartNewSession}
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
          </svg>
          <span>New Revision</span>
        </button>
      </div>

      <div className="space-y-3.5">
        {sessions.map((session) => {
          const isBusy = busySessionId === session.id;
          const isCompleted = session.status === "completed";
          const statusLabel = isCompleted ? "Completed" : "In Progress";
          const badgeClass = getStatusBadgeClasses(session.status);

          return (
            <div
              key={session.id}
              className="flex flex-col justify-between gap-4 rounded-xl border border-slate-200 bg-surface p-5 shadow-xs transition-shadow hover:shadow-sm sm:flex-row sm:items-center"
            >
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${badgeClass}`}
                  >
                    {statusLabel}
                  </span>
                  <span className="text-xs text-slate-400">
                    {formatDate(session.created_at)}
                  </span>
                  {session.config?.difficulty && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 capitalize">
                      {session.config.difficulty}
                    </span>
                  )}
                  {session.config?.mode && (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 capitalize">
                      {session.config.mode}
                    </span>
                  )}
                </div>

                <h2 className="text-sm font-semibold text-slate-900 truncate">
                  {session.title || "Revision Session"}
                </h2>

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <span>
                    <strong className="font-semibold text-slate-700">{session.total_questions}</strong> questions
                  </span>
                  {isCompleted && session.score !== null && (
                    <span>
                      Score:{" "}
                      <strong className="font-semibold text-emerald-700">
                        {formatPercentageScore(session.score)}
                      </strong>
                    </span>
                  )}
                  <span>
                    {session.document_ids?.length || 0} source {session.document_ids?.length === 1 ? "document" : "documents"}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex shrink-0 items-center gap-2">
                {!isCompleted ? (
                  <button
                    type="button"
                    onClick={() => handleResume(session)}
                    disabled={isBusy}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50"
                  >
                    {isBusy ? "Resuming..." : "Resume"}
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => handleReview(session)}
                      disabled={isBusy}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isBusy ? "Loading..." : "Review Results"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRetake(session)}
                      disabled={isBusy}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition-colors hover:border-slate-400 hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Retake
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default RevisionHistoryView;
