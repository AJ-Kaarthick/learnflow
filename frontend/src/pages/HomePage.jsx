import { useEffect, useRef, useState } from "react";
import { listDocuments } from "../api/documents.js";
import { getProgressRecommendations, getProgressWeakTopics } from "../api/progress.js";
import { getRevisionSession, listRevisionSessions } from "../api/revision.js";
import AuthPanel from "../components/AuthPanel.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { ROUTES, routeHref } from "../router/useHashRoute.js";
import {
  QUICK_ACTIONS,
  extractInProgressSession,
  formatGreetingTitle,
  formatInProgressSessionProgress,
  formatRecentDocumentDate,
  getGreetingSubtitle,
  getRecommendationActionText,
  getRecommendationBadge,
  getTopRecommendations,
  getTopWeakTopics,
  isRequestCurrent,
} from "../utils/homeState.js";
import { saveActiveDocumentId } from "../utils/persistence.js";
import {
  createLaunchPayloadFromRecommendation,
  createLaunchPayloadFromWeakTopic,
  formatStruggleIndex,
  formatUtcDate,
  getIdentityScope,
  savePendingRevisionLaunch,
} from "../utils/progressState.js";
import { savePendingRevisionResume } from "../utils/revisionState.js";

const RECENT_DOCUMENT_LIMIT = 5;

/**
 * LearnFlow Home Dashboard (V3 Milestone 6 Phase 3).
 *
 * Provides:
 * 1. Personalized, identity-aware greeting banner.
 * 2. Non-intrusive guest session callout with one-click access to AuthPanel.
 * 3. In-Progress Revision card with identity-safe one-click resume handoff.
 * 4. Action Center with top adaptive recommendations and Revision setup handoff.
 * 5. Focus Areas card spotlighting high-need weak topics with practice trigger.
 * 6. 4-way Workspace Quick Actions grid (Study, Revision, Chat, Progress).
 * 7. Preserved 'Continue studying' list for recently opened documents.
 */
function HomePage() {
  const { identity, isAuthenticated, status: authStatus } = useAuth();
  const currentScope = getIdentityScope(identity);
  const currentScopeRef = useRef(currentScope);
  currentScopeRef.current = currentScope;

  const recGenRef = useRef(0);
  const recAbortRef = useRef(null);
  const weakTopicsGenRef = useRef(0);
  const weakTopicsAbortRef = useRef(null);

  const [authPanelOpen, setAuthPanelOpen] = useState(false);
  const [authPanelMode, setAuthPanelMode] = useState("signup");

  const [recentDocuments, setRecentDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  const [inProgressSession, setInProgressSession] = useState(null);
  const [loadingSession, setLoadingSession] = useState(true);

  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(true);
  const [recommendationsError, setRecommendationsError] = useState(null);

  const [weakTopics, setWeakTopics] = useState([]);
  const [loadingWeakTopics, setLoadingWeakTopics] = useState(true);
  const [weakTopicsError, setWeakTopicsError] = useState(null);

  // Load recently opened documents scoped to current identity
  useEffect(() => {
    let cancelled = false;
    setLoadingDocs(true);

    listDocuments({ sort: "recently_opened" })
      .then((documents) => {
        if (cancelled) return;
        setRecentDocuments(
          (documents || []).filter((doc) => doc.last_opened_at).slice(0, RECENT_DOCUMENT_LIMIT)
        );
      })
      .catch(() => {
        // Degrade gracefully; leave recentDocuments empty
      })
      .finally(() => {
        if (!cancelled) setLoadingDocs(false);
      });

    return () => {
      cancelled = true;
    };
  }, [identity, authStatus]);

  // Load in-progress revision session scoped to current identity
  useEffect(() => {
    if (authStatus === "loading") {
      return;
    }

    let cancelled = false;
    setLoadingSession(true);

    listRevisionSessions()
      .then(async (sessions) => {
        if (cancelled) return;
        const candidate = extractInProgressSession(sessions);
        if (!candidate) {
          setInProgressSession(null);
          setLoadingSession(false);
          return;
        }

        // Set initial candidate with summary stats immediately
        setInProgressSession(candidate);
        setLoadingSession(false);

        // If candidate doesn't have answered questions count, fetch session detail
        if (candidate.answeredQuestions === null && candidate.id) {
          try {
            const detail = await getRevisionSession(candidate.id);
            if (!cancelled && detail) {
              const enriched = extractInProgressSession([detail]);
              if (enriched) {
                setInProgressSession(enriched);
              }
            }
          } catch {
            // Gracefully keep summary stats on detail fetch error
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setInProgressSession(null);
          setLoadingSession(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [identity, authStatus]);

  // Load adaptive recommendations and weak topics scoped to current identity
  useEffect(() => {
    // Invalidate outstanding requests/retries on identity or auth changes
    if (recAbortRef.current) recAbortRef.current.abort();
    if (weakTopicsAbortRef.current) weakTopicsAbortRef.current.abort();

    const nextRecGen = recGenRef.current + 1;
    recGenRef.current = nextRecGen;
    const nextWeakGen = weakTopicsGenRef.current + 1;
    weakTopicsGenRef.current = nextWeakGen;

    // Immediately isolate state across identities: clear previous data & errors
    setRecommendations([]);
    setRecommendationsError(null);
    setWeakTopics([]);
    setWeakTopicsError(null);

    if (authStatus === "loading" || !currentScope) {
      setLoadingRecommendations(true);
      setLoadingWeakTopics(true);
      return;
    }

    setLoadingRecommendations(true);
    setLoadingWeakTopics(true);

    const recController = new AbortController();
    recAbortRef.current = recController;
    const weakController = new AbortController();
    weakTopicsAbortRef.current = weakController;

    const boundScope = currentScope;

    // 1. Fetch top recommendations
    getProgressRecommendations({ limit: 2, signal: recController.signal })
      .then((data) => {
        if (isRequestCurrent(nextRecGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setRecommendations(getTopRecommendations(data, 2));
        }
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        if (isRequestCurrent(nextRecGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setRecommendationsError(err?.message || "Could not load recommendations.");
        }
      })
      .finally(() => {
        if (isRequestCurrent(nextRecGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setLoadingRecommendations(false);
        }
      });

    // 2. Fetch detected weak topics
    getProgressWeakTopics({ signal: weakController.signal })
      .then((data) => {
        if (isRequestCurrent(nextWeakGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setWeakTopics(getTopWeakTopics(data, 2));
        }
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        if (isRequestCurrent(nextWeakGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setWeakTopicsError(err?.message || "Could not load weak topics.");
        }
      })
      .finally(() => {
        if (isRequestCurrent(nextWeakGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setLoadingWeakTopics(false);
        }
      });

    return () => {
      recController.abort();
      weakController.abort();
    };
  }, [currentScope, authStatus]);

  function retryRecommendations() {
    if (authStatus === "loading" || !currentScope) {
      return;
    }
    if (recAbortRef.current) {
      recAbortRef.current.abort();
    }
    const nextGen = recGenRef.current + 1;
    recGenRef.current = nextGen;
    const boundScope = currentScope;

    setLoadingRecommendations(true);
    setRecommendationsError(null);

    const controller = new AbortController();
    recAbortRef.current = controller;

    getProgressRecommendations({ limit: 2, signal: controller.signal })
      .then((data) => {
        if (isRequestCurrent(nextGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setRecommendations(getTopRecommendations(data, 2));
        }
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        if (isRequestCurrent(nextGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setRecommendationsError(err?.message || "Could not load recommendations.");
        }
      })
      .finally(() => {
        if (isRequestCurrent(nextGen, boundScope, recGenRef.current, currentScopeRef.current)) {
          setLoadingRecommendations(false);
        }
      });
  }

  function retryWeakTopics() {
    if (authStatus === "loading" || !currentScope) {
      return;
    }
    if (weakTopicsAbortRef.current) {
      weakTopicsAbortRef.current.abort();
    }
    const nextGen = weakTopicsGenRef.current + 1;
    weakTopicsGenRef.current = nextGen;
    const boundScope = currentScope;

    setLoadingWeakTopics(true);
    setWeakTopicsError(null);

    const controller = new AbortController();
    weakTopicsAbortRef.current = controller;

    getProgressWeakTopics({ signal: controller.signal })
      .then((data) => {
        if (isRequestCurrent(nextGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setWeakTopics(getTopWeakTopics(data, 2));
        }
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        if (isRequestCurrent(nextGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setWeakTopicsError(err?.message || "Could not load weak topics.");
        }
      })
      .finally(() => {
        if (isRequestCurrent(nextGen, boundScope, weakTopicsGenRef.current, currentScopeRef.current)) {
          setLoadingWeakTopics(false);
        }
      });
  }

  function handleContinueStudying(doc) {
    saveActiveDocumentId(doc.id);
  }

  function handleResumeSession(sessionId) {
    savePendingRevisionResume(sessionId, identity);
  }

  function handleLaunchRecommendation(rec) {
    if (!rec || !rec.isActionable || rec.isArchived) {
      return;
    }
    const payload = createLaunchPayloadFromRecommendation(rec);
    if (!payload) {
      return;
    }
    const success = savePendingRevisionLaunch(payload, identity);
    if (success) {
      window.location.hash = routeHref(ROUTES.REVISION);
    }
  }

  function handleLaunchWeakTopic(topic) {
    if (!topic || !topic.isActionable || topic.isArchived || !topic.documentId) {
      return;
    }
    const payload = createLaunchPayloadFromWeakTopic({
      document_id: topic.documentId,
      topic_display: topic.topicDisplay,
      topic_key: topic.topicKey,
    });
    if (!payload) {
      return;
    }
    const success = savePendingRevisionLaunch(payload, identity);
    if (success) {
      window.location.hash = routeHref(ROUTES.REVISION);
    }
  }

  return (
    <main aria-label="Home Dashboard" className="min-w-0 flex-1 overflow-y-auto p-6 lg:p-10">
      <div className="mx-auto max-w-4xl space-y-8">
        {/* Header Greeting */}
        <header className="space-y-1.5" aria-label="Welcome">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {formatGreetingTitle(identity)}
          </h1>
          <p className="text-sm text-slate-500">
            {getGreetingSubtitle(identity)}
          </p>
        </header>

        {/* Guest Session Account Callout */}
        {!isAuthenticated && authStatus !== "loading" && (
          <aside
            role="region"
            aria-label="Guest Session Information"
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-accent-200 bg-accent-50/60 p-4 text-sm"
          >
            <div className="space-y-1">
              <p className="font-semibold text-accent-900">
                Exploring as a guest
              </p>
              <p className="text-xs text-accent-700">
                Your uploaded documents, revision sessions, and progress are saved in this browser. Create a free account anytime to secure your learning history across devices.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setAuthPanelMode("signup");
                  setAuthPanelOpen(true);
                }}
                className="rounded-lg bg-accent-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Create Account
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthPanelMode("signin");
                  setAuthPanelOpen(true);
                }}
                className="rounded-lg border border-slate-300 bg-surface px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
              >
                Sign In
              </button>
            </div>
          </aside>
        )}

        {/* In-Progress Revision Card */}
        {inProgressSession && (
          <section aria-label="In-Progress Revision" className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-slate-900">
                Continue revision
              </h2>
              <span className="text-xs font-medium text-amber-700">Active session</span>
            </div>

            <div
              data-testid="in-progress-revision-card"
              className="relative overflow-hidden rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/60 via-surface to-white p-5 shadow-2xs transition-all hover:border-amber-300"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-2 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                      In Progress
                    </span>
                    {inProgressSession.difficulty && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium capitalize text-slate-600">
                        {inProgressSession.difficulty}
                      </span>
                    )}
                    {inProgressSession.mode && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium capitalize text-slate-600">
                        {inProgressSession.mode}
                      </span>
                    )}
                  </div>

                  <h3 className="truncate text-base font-semibold text-slate-900">
                    {inProgressSession.title}
                  </h3>

                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>{formatInProgressSessionProgress(inProgressSession)}</span>
                    {inProgressSession.progressPercentage !== null && (
                      <span className="font-medium text-slate-600">({inProgressSession.progressPercentage}%)</span>
                    )}
                  </div>

                  {inProgressSession.progressPercentage !== null && (
                    <div className="w-full max-w-xs h-1.5 rounded-full bg-slate-200/80 overflow-hidden">
                      <div
                        className="h-full bg-amber-600 rounded-full transition-all duration-300"
                        style={{ width: `${Math.max(0, Math.min(100, inProgressSession.progressPercentage))}%` }}
                      />
                    </div>
                  )}
                </div>

                <div className="flex shrink-0 items-center">
                  <a
                    href={routeHref(ROUTES.REVISION)}
                    onClick={() => handleResumeSession(inProgressSession.id)}
                    aria-label={`Resume revision session: ${inProgressSession.title}`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 transition-colors"
                  >
                    <span>Resume Session</span>
                    <span aria-hidden="true">→</span>
                  </a>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Action Center: Adaptive Recommendations */}
        <section aria-label="Action Center" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">
              Recommended next steps
            </h2>
            <a
              href={routeHref(ROUTES.PROGRESS)}
              className="text-xs font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              View progress analytics →
            </a>
          </div>

          {recommendationsError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{recommendationsError}</span>
              <button
                type="button"
                onClick={retryRecommendations}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry
              </button>
            </div>
          ) : loadingRecommendations ? (
            <div className="rounded-xl border border-slate-200 bg-surface p-6 text-center text-xs text-slate-400">
              <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2 align-middle" />
              Loading recommendations...
            </div>
          ) : recommendations.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-xs text-slate-400">
              No active revision recommendations. You are all caught up!
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {recommendations.map((rec) => {
                const badge = getRecommendationBadge(rec.type);
                const actionText = getRecommendationActionText(rec);
                const isActionable = rec.isActionable && !rec.isArchived;

                return (
                  <div
                    key={rec.id}
                    data-testid="recommendation-card"
                    className={`flex flex-col justify-between rounded-xl border p-5 transition-all ${
                      isActionable
                        ? "border-slate-200 bg-surface hover:border-slate-300 hover:shadow-2xs"
                        : "border-slate-200/60 bg-slate-50/50 opacity-75"
                    }`}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badge.badgeClasses}`}>
                          {badge.label}
                        </span>
                        {rec.dueDate && (
                          <span className="text-[10px] text-slate-400">
                            Due {formatUtcDate(rec.dueDate)}
                          </span>
                        )}
                      </div>

                      <h3 className="text-sm font-semibold text-slate-900 leading-snug">
                        {rec.title}
                      </h3>

                      <p className="text-xs text-slate-500 leading-relaxed">
                        {rec.reason}
                      </p>

                      <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-500">
                        <span className="font-medium text-slate-700 truncate max-w-[200px]" title={rec.documentTitle}>
                          📄 {rec.documentTitle}
                        </span>
                        {rec.topicFocus && (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                            Focus: {rec.topicFocus}
                          </span>
                        )}
                        {rec.struggleIndex !== null && (
                          <span className="text-rose-600 font-medium">
                            Struggle: {formatStruggleIndex(rec.struggleIndex)}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end">
                      <button
                        type="button"
                        onClick={() => handleLaunchRecommendation(rec)}
                        disabled={!isActionable}
                        aria-label={`Launch revision for recommendation: ${rec.title}`}
                        className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold shadow-2xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 ${
                          isActionable
                            ? "bg-accent-600 text-white hover:bg-accent-700"
                            : "cursor-not-allowed bg-slate-100 text-slate-400 border border-slate-200"
                        }`}
                      >
                        <span>{actionText}</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Weak Areas Card */}
        <section aria-label="Weak Topics" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">
              Focus areas
            </h2>
            <span className="text-xs text-slate-400">High-need topics</span>
          </div>

          {weakTopicsError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 flex items-center justify-between">
              <span>{weakTopicsError}</span>
              <button
                type="button"
                onClick={retryWeakTopics}
                className="rounded bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800 hover:bg-red-200"
              >
                Retry
              </button>
            </div>
          ) : loadingWeakTopics ? (
            <div className="rounded-xl border border-slate-200 bg-surface p-6 text-center text-xs text-slate-400">
              <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent-600 border-t-transparent mr-2 align-middle" />
              Loading focus areas...
            </div>
          ) : weakTopics.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-surface p-5 text-center text-xs text-slate-600">
              <p className="font-semibold text-slate-900">No practice-ready weak topics right now.</p>
              <p className="mt-1 text-slate-500">
                Review your complete topic history and learning insights in{" "}
                <a
                  href={routeHref(ROUTES.PROGRESS)}
                  className="font-medium text-accent-700 hover:text-accent-800 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 rounded-xs"
                >
                  Progress
                </a>
                .
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {weakTopics.map((wt) => {
                const isActionable = wt.isActionable && !wt.isArchived;

                return (
                  <div
                    key={`${wt.documentId || "archived"}:${wt.topicKey}`}
                    data-testid="weak-topic-card"
                    className="flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-4 shadow-2xs"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="rounded-full bg-rose-50 border border-rose-200 px-2 py-0.5 text-[10px] font-semibold text-rose-700">
                          Needs Practice
                        </span>
                        {wt.struggleIndex !== null && (
                          <span className="text-[10px] font-medium text-rose-600">
                            Struggle: {formatStruggleIndex(wt.struggleIndex)}
                          </span>
                        )}
                      </div>

                      <h3 className="text-sm font-semibold text-slate-900 truncate" title={wt.topicDisplay}>
                        {wt.topicDisplay}
                      </h3>

                      <p className="text-xs text-slate-500 truncate" title={wt.documentTitle}>
                        📄 {wt.documentTitle}
                      </p>
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
                      <span className="text-[11px] text-slate-400">
                        {wt.totalAttempts} {wt.totalAttempts === 1 ? "attempt" : "attempts"}
                      </span>
                      {isActionable ? (
                        <button
                          type="button"
                          onClick={() => handleLaunchWeakTopic(wt)}
                          aria-label={`Practice weak topic: ${wt.topicDisplay}`}
                          className="rounded-lg bg-accent-600 px-3 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 transition-colors"
                        >
                          Practice Topic →
                        </button>
                      ) : (
                        <span className="rounded bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-400 border border-slate-200">
                          {wt.isArchived ? "Archived" : "Not Ready"}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* 4-way Workspace Quick Actions Grid */}
        <section aria-label="Workspace Quick Actions" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">Workspaces</h2>
            <span className="text-xs text-slate-400">Quick launch</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {QUICK_ACTIONS.map((action) => (
              <a
                key={action.id}
                href={routeHref(action.route)}
                aria-label={action.ariaLabel}
                className="group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-surface p-5 transition-all hover:border-accent-300 hover:bg-accent-50/30 hover:shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-base font-semibold text-slate-900 group-hover:text-accent-700">
                      {action.title}
                    </p>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 group-hover:bg-accent-100 group-hover:text-accent-800">
                      {action.badge}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
                    {action.description}
                  </p>
                </div>
                <div className="mt-3 flex items-center gap-1 text-xs font-medium text-accent-700 group-hover:text-accent-800">
                  <span>Open workspace</span>
                  <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">→</span>
                </div>
              </a>
            ))}
          </div>
        </section>

        {/* Continue Studying (Recently Opened Documents) */}
        <section aria-label="Continue Studying" className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">Continue studying</h2>
            <a
              href={routeHref(ROUTES.STUDY)}
              className="shrink-0 text-xs font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              View all documents →
            </a>
          </div>

          {loadingDocs ? (
            <div className="rounded-xl border border-slate-200 bg-surface p-6 text-center text-xs text-slate-400">
              Loading recent documents...
            </div>
          ) : recentDocuments.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center">
              <p className="text-sm font-medium text-slate-700">No documents opened yet</p>
              <p className="mt-1 text-xs text-slate-400">
                Head to{" "}
                <a href={routeHref(ROUTES.STUDY)} className="font-medium text-accent-700 hover:text-accent-800">
                  Study
                </a>{" "}
                to upload and open your first document.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-surface shadow-2xs">
              {recentDocuments.map((doc) => (
                <li key={doc.id}>
                  <a
                    href={routeHref(ROUTES.STUDY)}
                    onClick={() => handleContinueStudying(doc)}
                    className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
                  >
                    <span className="min-w-0 truncate text-sm font-medium text-slate-800">
                      {doc.original_filename}
                    </span>
                    <span className="shrink-0 text-xs text-slate-400">
                      Opened {formatRecentDocumentDate(doc.last_opened_at)}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Auth Modal when triggered from guest banner */}
        {authPanelOpen && (
          <AuthPanel
            onClose={() => setAuthPanelOpen(false)}
            initialMode={authPanelMode}
          />
        )}
      </div>
    </main>
  );
}

export default HomePage;
