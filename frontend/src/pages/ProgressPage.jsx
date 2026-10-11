import { useCallback, useEffect, useRef, useState } from "react";
import {
  getProgressRecommendations,
  getProgressSummary,
  getProgressTopics,
  getProgressWeakTopics,
  getSpacedRepetitionSchedules,
} from "../api/progress.js";
import { useAuth } from "../context/AuthContext.jsx";
import {
  VOLUME_METRICS,
  computeActivityChartData,
  createLaunchPayloadFromRecommendation,
  createLaunchPayloadFromSchedule,
  createLaunchPayloadFromWeakTopic,
  formatIntervalDays,
  formatMasteryTier,
  formatPercent,
  formatScore,
  formatStruggleIndex,
  formatUrgency,
  formatUtcDate,
  getIdentityScope,
  savePendingRevisionLaunch,
} from "../utils/progressState.js";

/**
 * Top-level Learner Progress Workspace (V3 Milestone 5 Phase 4).
 *
 * Provides:
 * 1. Overview KPIs (Overall Mastery, Sessions, Questions, Accuracy, Flashcard Recall)
 * 2. Activity Trends Dual-Axis SVG Chart (7, 14, 30 days; questions/sessions/attempts toggle; null score gaps)
 * 3. Difficulty & Flashcard Performance Breakdowns
 * 4. Priority-Ranked Adaptive Recommendations with canonical Revision setup handoff
 * 5. Weak-Topic Practice Spotlight with Struggle Index
 * 6. Spaced Repetition Document Review Schedules with Due Indicators
 * 7. Composite Topic Mastery Explorer with Document Provenance
 *
 * Architecture:
 * - Independent resource states (summary, topics, weakTopics, schedules, recommendations)
 * - Section-level failure resilience and retry
 * - Immediate identity change isolation during auth loading
 * - AbortController and generation guards against stale responses
 */
function ProgressPage() {
  const { identity, status: authStatus } = useAuth();
  const currentScope = getIdentityScope(identity);

  // Independent resource states for resilience
  const [summaryState, setSummaryState] = useState({ data: null, loading: true, error: null });
  const [topicsState, setTopicsState] = useState({ data: null, loading: true, error: null });
  const [weakTopicsState, setWeakTopicsState] = useState({ data: null, loading: true, error: null });
  const [schedulesState, setSchedulesState] = useState({ data: null, loading: true, error: null });
  const [recommendationsState, setRecommendationsState] = useState({ data: null, loading: true, error: null });

  // Global manual refresh indicator
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Chart configuration
  const [activeWindowDays, setActiveWindowDays] = useState(7); // 7 | 14 | 30
  const [volumeMetric, setVolumeMetric] = useState("questions_attempted");

  // Filter for recommendations
  const [recFilter, setRecFilter] = useState("all"); // "all" | "spaced_review" | "weak_topic_practice" | "unrevised_document"

  // Generation guard & abort controller refs
  const generationRef = useRef(0);
  const abortControllerRef = useRef(null);
  const previousScopeRef = useRef(null);

  // Individual loaders
  const loadSummary = useCallback(async (signal, gen) => {
    setSummaryState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getProgressSummary({ signal });
      if (generationRef.current === gen) {
        setSummaryState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (generationRef.current === gen) {
        setSummaryState((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || "Could not load progress summary.",
        }));
      }
    }
  }, []);

  const loadTopics = useCallback(async (signal, gen) => {
    setTopicsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getProgressTopics({ signal });
      if (generationRef.current === gen) {
        setTopicsState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (generationRef.current === gen) {
        setTopicsState((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || "Could not load topic mastery.",
        }));
      }
    }
  }, []);

  const loadWeakTopics = useCallback(async (signal, gen) => {
    setWeakTopicsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getProgressWeakTopics({ signal });
      if (generationRef.current === gen) {
        setWeakTopicsState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (generationRef.current === gen) {
        setWeakTopicsState((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || "Could not load weak topics.",
        }));
      }
    }
  }, []);

  const loadSchedules = useCallback(async (signal, gen) => {
    setSchedulesState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getSpacedRepetitionSchedules({ includeUnreviewedActive: true, signal });
      if (generationRef.current === gen) {
        setSchedulesState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (generationRef.current === gen) {
        setSchedulesState((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || "Could not load review schedules.",
        }));
      }
    }
  }, []);

  const loadRecommendations = useCallback(async (signal, gen) => {
    setRecommendationsState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getProgressRecommendations({ signal });
      if (generationRef.current === gen) {
        setRecommendationsState({ data, loading: false, error: null });
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (generationRef.current === gen) {
        setRecommendationsState((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || "Could not load recommendations.",
        }));
      }
    }
  }, []);

  const loadAll = useCallback(
    (signal, gen) => {
      loadSummary(signal, gen);
      loadTopics(signal, gen);
      loadWeakTopics(signal, gen);
      loadSchedules(signal, gen);
      loadRecommendations(signal, gen);
    },
    [loadSummary, loadTopics, loadWeakTopics, loadSchedules, loadRecommendations]
  );

  // Identity change isolation:
  // When the identity scope changes, immediately clear all old identity data
  // so no stale metrics or recommendations remain visible while auth is loading!
  useEffect(() => {
    if (currentScope !== previousScopeRef.current) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      generationRef.current += 1;

      // Immediately clear state for previous identity
      setSummaryState({ data: null, loading: true, error: null });
      setTopicsState({ data: null, loading: true, error: null });
      setWeakTopicsState({ data: null, loading: true, error: null });
      setSchedulesState({ data: null, loading: true, error: null });
      setRecommendationsState({ data: null, loading: true, error: null });

      previousScopeRef.current = currentScope;
    }

    if (authStatus === "loading" || !currentScope) {
      // Do not initiate requests until identity is resolved
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentGen = generationRef.current;

    loadAll(controller.signal, currentGen);

    return () => {
      controller.abort();
    };
  }, [currentScope, authStatus, loadAll]);

  // Manual refresh of all resources
  const handleManualRefresh = () => {
    if (authStatus === "loading" || !currentScope) return;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const newGen = generationRef.current + 1;
    generationRef.current = newGen;

    setIsRefreshing(true);
    loadAll(controller.signal, newGen);

    Promise.allSettled([
      getProgressSummary({ signal: controller.signal }),
      getProgressTopics({ signal: controller.signal }),
      getProgressWeakTopics({ signal: controller.signal }),
      getSpacedRepetitionSchedules({ includeUnreviewedActive: true, signal: controller.signal }),
      getProgressRecommendations({ signal: controller.signal }),
    ]).finally(() => {
      if (generationRef.current === newGen) {
        setIsRefreshing(false);
      }
    });
  };

  // Section retry handlers
  const retrySummary = () => {
    if (authStatus === "loading" || !currentScope) return;
    loadSummary(abortControllerRef.current?.signal, generationRef.current);
  };
  const retryTopics = () => {
    if (authStatus === "loading" || !currentScope) return;
    loadTopics(abortControllerRef.current?.signal, generationRef.current);
  };
  const retryWeakTopics = () => {
    if (authStatus === "loading" || !currentScope) return;
    loadWeakTopics(abortControllerRef.current?.signal, generationRef.current);
  };
  const retrySchedules = () => {
    if (authStatus === "loading" || !currentScope) return;
    loadSchedules(abortControllerRef.current?.signal, generationRef.current);
  };
  const retryRecommendations = () => {
    if (authStatus === "loading" || !currentScope) return;
    loadRecommendations(abortControllerRef.current?.signal, generationRef.current);
  };

  // Handoff to Revision launcher
  function handleLaunchRecommendation(rec) {
    if (!rec || !rec.is_actionable || rec.is_archived) return;
    const payload = createLaunchPayloadFromRecommendation(rec);
    if (!payload) return;

    const saved = savePendingRevisionLaunch(payload, identity);
    if (saved) {
      window.location.hash = "#/revision";
    }
  }

  function handleLaunchWeakTopic(wt) {
    if (!wt || !wt.is_actionable || wt.is_archived) return;
    const payload = createLaunchPayloadFromWeakTopic(wt);
    if (!payload) return;

    const saved = savePendingRevisionLaunch(payload, identity);
    if (saved) {
      window.location.hash = "#/revision";
    }
  }

  function handleLaunchSchedule(sch) {
    if (!sch || !sch.is_actionable || sch.is_archived) return;
    const payload = createLaunchPayloadFromSchedule(sch);
    if (!payload) return;

    const saved = savePendingRevisionLaunch(payload, identity);
    if (saved) {
      window.location.hash = "#/revision";
    }
  }

  // Identity is still resolving: render loading shell without leaking prior identity data
  if (authStatus === "loading" || !currentScope) {
    return (
      <main aria-label="Progress Workspace" className="min-w-0 flex-1 min-h-0 overflow-y-auto bg-slate-50/50 py-6">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-surface p-12 shadow-2xs">
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-600 border-t-transparent" />
              <p className="text-xs font-medium text-slate-500">Resolving identity...</p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const summary = summaryState.data;
  const topics = topicsState.data;
  const weakTopics = weakTopicsState.data;
  const schedules = schedulesState.data;
  const recommendations = recommendationsState.data;

  // Activity timeline computation
  const activeWindowSummary =
    activeWindowDays === 14
      ? summary?.activity_windows?.last_14_days
      : activeWindowDays === 30
      ? summary?.activity_windows?.last_30_days
      : summary?.activity_windows?.last_7_days;

  const chartData = computeActivityChartData(activeWindowSummary?.timeline || [], {
    width: 640,
    height: 220,
    volumeMetric,
  });

  const selectedVolumeMeta = VOLUME_METRICS.find((m) => m.id === volumeMetric) || VOLUME_METRICS[0];

  // Recommendations filtering
  const filteredRecs = (recommendations || []).filter((rec) => {
    if (recFilter === "all") return true;
    return rec.type === recFilter;
  });

  const overallMasteryInfo = formatMasteryTier(
    summary?.overall_mastery?.tier,
    summary?.overall_mastery?.is_assessed ?? false
  );

  return (
    <main aria-label="Progress Workspace" className="min-w-0 flex-1 min-h-0 overflow-y-auto bg-slate-50/50 py-6">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-accent-100 px-2 py-0.5 text-xs font-semibold text-accent-700">
                Learning Progress
              </span>
              <span className="text-xs text-slate-400">On-demand intelligence</span>
            </div>
            <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Learner Analytics &amp; Recommendations
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Grounded insights, recency-decayed mastery, spaced repetition schedules, and adaptive practice.
            </p>
          </div>
          <div>
            <button
              type="button"
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-surface px-3.5 py-2 text-xs font-medium text-slate-700 shadow-2xs transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50"
            >
              <svg
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14 8A6 6 0 1 1 8 2c2.1 0 3.9 1.1 5 2.7M13.5 1.5v3h-3"
                />
              </svg>
              {isRefreshing ? "Refreshing..." : "Refresh Analytics"}
            </button>
          </div>
        </div>

        {/* Overview KPIs & Activity Trends */}
        {summaryState.error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <p className="font-semibold">Unable to Load Summary Analytics</p>
              <p className="mt-1 text-xs text-red-600">{summaryState.error}</p>
            </div>
            <button
              type="button"
              onClick={retrySummary}
              className="self-start sm:self-center rounded bg-red-100 px-3 py-1.5 text-xs font-semibold text-red-800 hover:bg-red-200"
            >
              Retry Summary
            </button>
          </div>
        ) : summaryState.loading && !summary ? (
          <div className="flex h-48 items-center justify-center rounded-xl border border-slate-200 bg-surface p-6 shadow-2xs">
            <div className="flex flex-col items-center gap-2">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent-600 border-t-transparent" />
              <p className="text-xs text-slate-500">Loading overview KPIs &amp; trends...</p>
            </div>
          </div>
        ) : summary ? (
          <>
            {/* Overview KPI Cards */}
            <section aria-label="Key Performance Indicators" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* Overall Mastery */}
              <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">Overall Mastery</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${overallMasteryInfo.badgeClasses}`}>
                    {overallMasteryInfo.label}
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-bold tracking-tight text-slate-900">
                    {summary.overall_mastery?.is_assessed ? formatPercent(summary.overall_mastery?.score) : "--"}
                  </span>
                  {!summary.overall_mastery?.is_assessed && (
                    <span className="text-xs text-slate-400">Unassessed</span>
                  )}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {summary.overall_mastery?.is_assessed
                    ? `${summary.overall_mastery?.attempted_count ?? 0} questions assessed with recency decay`
                    : `Requires ${summary.overall_mastery?.questions_needed ?? 3} questions to establish baseline`}
                </p>
              </div>

              {/* Completed Sessions */}
              <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
                <span className="text-xs font-medium text-slate-500">Completed Sessions</span>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-bold tracking-tight text-slate-900">
                    {summary.total_completed_sessions}
                  </span>
                  <span className="text-xs text-slate-400">sessions</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {summary.total_attempted_questions} of {summary.total_questions_generated} generated questions practiced
                </p>
              </div>

              {/* Accuracy & Mean Score */}
              <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
                <span className="text-xs font-medium text-slate-500">Attempt Accuracy</span>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-bold tracking-tight text-slate-900">
                    {summary.total_attempts > 0 ? formatPercent(summary.overall_attempt_accuracy) : "--"}
                  </span>
                  {summary.total_attempts > 0 && <span className="text-xs text-slate-400">accuracy</span>}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Mean completed score: {summary.total_completed_sessions > 0 ? formatPercent(summary.mean_session_score) : "--"} across {summary.total_attempts} attempts
                </p>
              </div>

              {/* Flashcard Recall */}
              <div className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">Flashcard Recall</span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                      formatMasteryTier(summary.flashcard_metrics?.mastery?.tier, summary.flashcard_metrics?.mastery?.is_assessed).badgeClasses
                    }`}
                  >
                    {formatMasteryTier(summary.flashcard_metrics?.mastery?.tier, summary.flashcard_metrics?.mastery?.is_assessed).label}
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-bold tracking-tight text-slate-900">
                    {formatPercent(summary.flashcard_metrics?.recall_rate)}
                  </span>
                  <span className="text-xs text-slate-400">recall rate</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {summary.flashcard_metrics?.distinct_questions_reviewed ?? 0} distinct flashcards reviewed
                </p>
              </div>
            </section>

            {/* Activity Trends Section */}
            <section aria-label="Activity Trends" className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Activity Timeline</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Dual-axis view of revision volume and average score trend across UTC calendar days.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* Volume Metric Selector */}
                  <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                    {VOLUME_METRICS.map((vm) => (
                      <button
                        key={vm.id}
                        type="button"
                        onClick={() => setVolumeMetric(vm.id)}
                        className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                          volumeMetric === vm.id
                            ? "bg-surface text-slate-900 shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        {vm.label}
                      </button>
                    ))}
                  </div>

                  {/* Window Days Selector */}
                  <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                    {[7, 14, 30].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setActiveWindowDays(d)}
                        className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                          activeWindowDays === d
                            ? "bg-surface text-slate-900 shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        {d} Days
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Chart Canvas */}
              <div className="mt-4">
                {chartData.isEmpty ? (
                  <div className="flex h-48 items-center justify-center text-xs text-slate-400">
                    No revision activity recorded in this window.
                  </div>
                ) : (
                  <div className="w-full overflow-x-auto">
                    <svg
                      viewBox={`0 0 ${chartData.width} ${chartData.height}`}
                      className="w-full h-auto max-h-64 select-none"
                      role="img"
                      aria-label="Activity timeline chart showing volume bars and average score trend line"
                    >
                      {/* Background grid lines */}
                      <line
                        x1={chartData.padding.left}
                        y1={chartData.padding.top}
                        x2={chartData.width - chartData.padding.right}
                        y2={chartData.padding.top}
                        stroke="#e2e8f0"
                        strokeDasharray="3 3"
                      />
                      <line
                        x1={chartData.padding.left}
                        y1={chartData.padding.top + (chartData.height - chartData.padding.top - chartData.padding.bottom) / 2}
                        x2={chartData.width - chartData.padding.right}
                        y2={chartData.padding.top + (chartData.height - chartData.padding.top - chartData.padding.bottom) / 2}
                        stroke="#e2e8f0"
                        strokeDasharray="3 3"
                      />
                      <line
                        x1={chartData.padding.left}
                        y1={chartData.height - chartData.padding.bottom}
                        x2={chartData.width - chartData.padding.right}
                        y2={chartData.height - chartData.padding.bottom}
                        stroke="#cbd5e1"
                      />

                      {/* Volume Bars */}
                      {chartData.bars.map((bar) => (
                        <rect
                          key={bar.date}
                          x={bar.x}
                          y={bar.y}
                          width={bar.width}
                          height={Math.max(1, bar.height)}
                          rx="2"
                          className="fill-accent-500/80 transition-colors hover:fill-accent-600"
                        >
                          <title>{`${bar.fullDateLabel}: ${bar.value} ${selectedVolumeMeta.label.toLowerCase()}`}</title>
                        </rect>
                      ))}

                      {/* Score Trend Line Segments (Gaps preserved across null days!) */}
                      {chartData.scoreSegments.map((segment, idx) => (
                        <polyline
                          key={idx}
                          points={segment}
                          fill="none"
                          stroke="#059669"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      ))}

                      {/* Score Dots */}
                      {chartData.scorePoints.map((pt) => (
                        <circle
                          key={pt.date}
                          cx={pt.x}
                          cy={pt.y}
                          r="3.5"
                          className="fill-white stroke-emerald-600 transition-transform hover:scale-125"
                          strokeWidth="2"
                        >
                          <title>{`${pt.dateLabel}: ${pt.scorePercent} average score`}</title>
                        </circle>
                      ))}

                      {/* X Axis Date Labels */}
                      {chartData.xLabels.map((lbl) => (
                        <text
                          key={lbl.date}
                          x={lbl.x}
                          y={chartData.height - 12}
                          textAnchor="middle"
                          className="fill-slate-500 text-[10px]"
                        >
                          {lbl.label}
                        </text>
                      ))}
                    </svg>

                    {/* Chart Legend */}
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1.5">
                          <span className="h-3 w-3 rounded-xs bg-accent-500/80" />
                          <span>{selectedVolumeMeta.label} (bars)</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="h-0.5 w-4 bg-emerald-600" />
                          <span>Daily Average Score (trend)</span>
                        </div>
                      </div>
                      <span className="text-[11px] text-slate-400">
                        *Gaps in the trend line indicate days without scored activity.
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Performance Breakdowns */}
            <section aria-label="Difficulty Breakdown" className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {(summary.difficulty_distribution || []).map((diff) => {
                const diffTier = formatMasteryTier(diff.mastery?.tier, diff.mastery?.is_assessed);
                return (
                  <div key={diff.difficulty} className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs">
                    <div className="flex items-center justify-between">
                      <span className="capitalize font-semibold text-sm text-slate-900">
                        {diff.difficulty}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${diffTier.badgeClasses}`}>
                        {diffTier.label}
                      </span>
                    </div>
                    <div className="mt-3 flex items-baseline gap-2">
                      <span className="text-2xl font-bold text-slate-900">
                        {diff.average_score !== null ? formatPercent(diff.average_score) : "--"}
                      </span>
                      <span className="text-xs text-slate-400">avg score</span>
                    </div>
                    <div className="mt-3 space-y-1 text-xs text-slate-500">
                      <div className="flex justify-between">
                        <span>Distinct Questions:</span>
                        <span className="font-medium text-slate-700">{diff.distinct_attempted_questions}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Total Attempts:</span>
                        <span className="font-medium text-slate-700">{diff.total_attempts}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </section>
          </>
        ) : null}

        {/* Adaptive Recommendations (Canonical Revision Setup Handoff) */}
        <section aria-label="Adaptive Recommendations" className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Adaptive Practice Recommendations</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Deterministic suggestions strictly following M5 priority: Spaced Reviews → Weak Topics → Unrevised Documents.
              </p>
            </div>
            {/* Filter Pills */}
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
              {[
                { id: "all", label: "All" },
                { id: "spaced_review", label: "Due Reviews" },
                { id: "weak_topic_practice", label: "Weak Topics" },
                { id: "unrevised_document", label: "Unrevised" },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setRecFilter(f.id)}
                  className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                    recFilter === f.id
                      ? "bg-surface text-slate-900 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {recommendationsState.error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{recommendationsState.error}</span>
              <button
                type="button"
                onClick={retryRecommendations}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry Recommendations
              </button>
            </div>
          ) : recommendationsState.loading && !recommendations ? (
            <div className="flex h-32 items-center justify-center text-xs text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2" />
              Loading recommendations...
            </div>
          ) : filteredRecs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400">
              No active recommendations in this category. You are up to date!
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {filteredRecs.map((rec) => {
                const urgencyInfo = formatUrgency(rec.urgency);
                const isActionable = rec.is_actionable && !rec.is_archived;

                return (
                  <div
                    key={rec.id}
                    className={`flex flex-col justify-between rounded-xl border p-4.5 transition-all ${
                      isActionable
                        ? "border-slate-200 bg-surface hover:border-slate-300 hover:shadow-xs"
                        : "border-slate-200/60 bg-slate-50/50 opacity-75"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                            rec.type === "spaced_review"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : rec.type === "weak_topic_practice"
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-blue-50 text-blue-700 border border-blue-200"
                          }`}
                        >
                          {rec.type === "spaced_review"
                            ? "Spaced Review"
                            : rec.type === "weak_topic_practice"
                            ? "Weak Topic Practice"
                            : "Unrevised Document"}
                        </span>
                        {rec.urgency !== null && (
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${urgencyInfo.badgeClasses}`}>
                            Urgency: {urgencyInfo.valueText}
                          </span>
                        )}
                      </div>

                      <h3 className="mt-2.5 text-sm font-semibold text-slate-900">{rec.title}</h3>
                      <p className="mt-1 text-xs text-slate-600 leading-relaxed">{rec.reason}</p>

                      {/* Provenance & details */}
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        <span className="font-medium text-slate-700 truncate max-w-[220px]" title={rec.document_title}>
                          📄 {rec.document_title}
                        </span>
                        {rec.topic_focus && (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                            Focus: {rec.topic_focus}
                          </span>
                        )}
                        {rec.struggle_index !== null && (
                          <span className="text-amber-700">
                            Struggle: {formatStruggleIndex(rec.struggle_index)}
                          </span>
                        )}
                        {rec.due_date && (
                          <span>Due: {formatUtcDate(rec.due_date)}</span>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                      <span className="text-[11px] text-slate-400">
                        {rec.action_payload?.question_count ?? 5} questions · {rec.action_payload?.mode ?? "practice"}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleLaunchRecommendation(rec)}
                        disabled={!isActionable}
                        className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold shadow-2xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                          isActionable
                            ? "bg-accent-600 text-white hover:bg-accent-700"
                            : "cursor-not-allowed bg-slate-200 text-slate-400"
                        }`}
                      >
                        {!isActionable ? (rec.is_archived ? "Archived" : "Not Ready") : "Start Revision →"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Weak Topics Spotlight */}
        <section aria-label="Weak Topics" className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs space-y-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Weak-Topic Detection</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Prioritized by struggle index and error ratio to help focus study on high-need areas.
            </p>
          </div>

          {weakTopicsState.error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{weakTopicsState.error}</span>
              <button
                type="button"
                onClick={retryWeakTopics}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry Weak Topics
              </button>
            </div>
          ) : weakTopicsState.loading && !weakTopics ? (
            <div className="flex h-32 items-center justify-center text-xs text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2" />
              Loading weak topics...
            </div>
          ) : !weakTopics || weakTopics.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400">
              No weak topics detected. Great progress across all assessed topics!
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400">
                    <th className="pb-2 font-medium">Topic</th>
                    <th className="pb-2 font-medium">Document</th>
                    <th className="pb-2 font-medium">Struggle Index</th>
                    <th className="pb-2 font-medium">Incorrect Ratio</th>
                    <th className="pb-2 font-medium">Mastery</th>
                    <th className="pb-2 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {weakTopics.map((wt, i) => {
                    const isActionable = wt.is_actionable && !wt.is_archived;
                    return (
                      <tr key={`${wt.document_id}-${wt.topic_key}-${i}`} className="hover:bg-slate-50/50">
                        <td className="py-3 font-medium text-slate-900">{wt.topic_display}</td>
                        <td className="py-3 text-slate-600 truncate max-w-[200px]" title={wt.document_title}>
                          {wt.document_title}
                        </td>
                        <td className="py-3 font-semibold text-amber-700">
                          {formatStruggleIndex(wt.struggle_index)}
                        </td>
                        <td className="py-3 text-slate-600">
                          {formatPercent(wt.incorrect_ratio)} ({wt.incorrect_questions_count}/{wt.distinct_attempted_questions})
                        </td>
                        <td className="py-3">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                              formatMasteryTier(wt.mastery_tier, true).badgeClasses
                            }`}
                          >
                            {formatMasteryTier(wt.mastery_tier, true).label}
                          </span>
                        </td>
                        <td className="py-3 text-right">
                          <button
                            type="button"
                            onClick={() => handleLaunchWeakTopic(wt)}
                            disabled={!isActionable}
                            className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                              isActionable
                                ? "bg-accent-50 text-accent-700 border border-accent-200 hover:bg-accent-100"
                                : "cursor-not-allowed bg-slate-100 text-slate-400 border border-slate-200"
                            }`}
                          >
                            {isActionable ? "Practice Topic" : wt.is_archived ? "Archived" : "Not Ready"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Spaced Repetition Schedules */}
        <section aria-label="Spaced Repetition" className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs space-y-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Spaced Repetition Schedule</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Document-level review intervals based on revision performance streaks.
            </p>
          </div>

          {schedulesState.error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{schedulesState.error}</span>
              <button
                type="button"
                onClick={retrySchedules}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry Schedules
              </button>
            </div>
          ) : schedulesState.loading && !schedules ? (
            <div className="flex h-32 items-center justify-center text-xs text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2" />
              Loading review schedules...
            </div>
          ) : !schedules || schedules.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400">
              No review schedules recorded yet. Complete revision sessions to establish review schedules.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400">
                    <th className="pb-2 font-medium">Document</th>
                    <th className="pb-2 font-medium">Streak</th>
                    <th className="pb-2 font-medium">Interval</th>
                    <th className="pb-2 font-medium">Latest Score</th>
                    <th className="pb-2 font-medium">Next Due</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {schedules.map((sch, i) => {
                    const isActionable = sch.is_actionable && !sch.is_archived;
                    return (
                      <tr key={`${sch.document_id}-${i}`} className="hover:bg-slate-50/50">
                        <td className="py-3 font-medium text-slate-900 truncate max-w-[220px]" title={sch.document_title}>
                          {sch.document_title}
                        </td>
                        <td className="py-3 text-slate-700 font-semibold">{sch.current_streak}</td>
                        <td className="py-3 text-slate-600">{formatIntervalDays(sch.interval_days)}</td>
                        <td className="py-3 text-slate-700">{formatScore(sch.latest_review_score)}</td>
                        <td className="py-3 text-slate-600">{formatUtcDate(sch.next_review_due)}</td>
                        <td className="py-3">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                              sch.is_due
                                ? "bg-rose-50 text-rose-700 border-rose-200"
                                : "bg-slate-50 text-slate-600 border-slate-200"
                            }`}
                          >
                            {sch.is_due ? "Review Due" : "Upcoming"}
                          </span>
                        </td>
                        <td className="py-3 text-right">
                          <button
                            type="button"
                            onClick={() => handleLaunchSchedule(sch)}
                            disabled={!isActionable}
                            className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                              isActionable
                                ? "bg-accent-50 text-accent-700 border border-accent-200 hover:bg-accent-100"
                                : "cursor-not-allowed bg-slate-100 text-slate-400 border border-slate-200"
                            }`}
                          >
                            {isActionable ? "Review Document" : sch.is_archived ? "Archived" : "Not Ready"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Topic Mastery Explorer */}
        <section aria-label="Topic Mastery" className="rounded-xl border border-slate-200 bg-surface p-5 shadow-2xs space-y-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Topic Mastery Explorer</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Comprehensive topic breakdown preserving composite document provenance.
            </p>
          </div>

          {topicsState.error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{topicsState.error}</span>
              <button
                type="button"
                onClick={retryTopics}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry Topics
              </button>
            </div>
          ) : topicsState.loading && !topics ? (
            <div className="flex h-32 items-center justify-center text-xs text-slate-400">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2" />
              Loading topic mastery...
            </div>
          ) : !topics || topics.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400">
              No topic mastery data found. Complete revision questions to populate topic mastery.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400">
                    <th className="pb-2 font-medium">Topic</th>
                    <th className="pb-2 font-medium">Source Document</th>
                    <th className="pb-2 font-medium">Mastery Score</th>
                    <th className="pb-2 font-medium">Tier</th>
                    <th className="pb-2 font-medium">Questions Attempted</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {topics.map((t, i) => {
                    const tierInfo = formatMasteryTier(t.mastery_tier, t.is_assessed);
                    return (
                      <tr key={`${t.document_id}-${t.topic_key}-${i}`} className="hover:bg-slate-50/50">
                        <td className="py-3 font-medium text-slate-900">{t.topic_display}</td>
                        <td className="py-3 text-slate-600 truncate max-w-[200px]" title={t.document_title}>
                          {t.document_title}
                          {t.is_archived && <span className="ml-1 text-[10px] text-amber-600">(archived)</span>}
                        </td>
                        <td className="py-3 font-semibold text-slate-900">
                          {t.is_assessed ? formatPercent(t.mastery_score) : "--"}
                        </td>
                        <td className="py-3">
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${tierInfo.badgeClasses}`}>
                            {tierInfo.label}
                          </span>
                        </td>
                        <td className="py-3 text-slate-600">{t.distinct_attempted_questions}</td>
                        <td className="py-3 text-[11px] text-slate-400">
                          {t.is_assessed ? "Assessed" : `${t.questions_needed} more needed`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export default ProgressPage;
