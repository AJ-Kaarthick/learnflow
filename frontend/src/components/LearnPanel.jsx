import { useEffect, useRef, useState } from "react";
import { generateLearnOutline, generateLearnTopic } from "../api/learn.js";
import { isGuestLimitError } from "../api/errors.js";
import GuestLimitNotice from "./GuestLimitNotice.jsx";
import LearnCurriculum from "./LearnCurriculum.jsx";
import LearnTopicViewer from "./LearnTopicViewer.jsx";
import {
  applyOutlineResponse,
  applyTopicResponse,
  findSubtopicById,
  findTopicById,
  getTopicContent,
  isSelectionOutdated,
  LEARN_DEPTHS,
} from "../utils/learnState.js";

function LearnPanel({
  selectedDocuments = [],
  session,
  onUpdateSession,
  isNoneReadable = false,
}) {
  const [outlineDepth, setOutlineDepth] = useState(session.activeDepth || "standard");
  const [loadingTopic, setLoadingTopic] = useState(false);
  const [loadingAction, setLoadingAction] = useState(null);

  // In-flight guard to prevent duplicate topic generation requests
  const topicRequestInFlightRef = useRef(false);

  // Extract all currently selected document IDs (full set sent to backend)
  const fullDocumentIds = selectedDocuments.map((doc) => doc.id);

  // Outline generation handler
  async function handleGenerateOutline() {
    if (isNoneReadable || fullDocumentIds.length === 0) return;

    onUpdateSession((prev) => ({
      ...prev,
      status: "generating_outline",
      errorMessage: "",
      generationError: null,
      activeDepth: outlineDepth,
    }));

    try {
      const outline = await generateLearnOutline({
        documentIds: fullDocumentIds,
        depth: outlineDepth,
      });

      const nextSession = applyOutlineResponse(session, outline);
      nextSession.activeDepth = outlineDepth;

      // Automatically select Topic 1
      const firstTopic = outline.topics?.[0];
      if (firstTopic) {
        nextSession.selectedTopicId = firstTopic.id;
      }

      onUpdateSession(() => nextSession);

      // Trigger first topic generation if available
      if (firstTopic) {
        await loadTopicContent({
          sessionOverride: nextSession,
          topicId: firstTopic.id,
          topicTitle: firstTopic.title,
          depth: outlineDepth,
          action: null,
        });
      }
    } catch (error) {
      onUpdateSession((prev) => ({
        ...prev,
        status: "error",
        errorMessage: error.message,
        generationError: error,
      }));
    }
  }

  // Topic content loader with caching and in-flight duplicate guard
  async function loadTopicContent({
    sessionOverride = null,
    topicId,
    topicTitle,
    parentTopicTitle = null,
    depth = "standard",
    action = null,
  }) {
    const currentSession = sessionOverride || session;

    // Check if content already exists in topicCache
    const cached = getTopicContent(currentSession, topicId, depth, action);
    if (cached) {
      onUpdateSession((prev) => ({
        ...prev,
        selectedTopicId: topicId,
        activeDepth: depth,
        activeAction: action,
        status: "idle",
        errorMessage: "",
        generationError: null,
      }));
      return;
    }

    if (topicRequestInFlightRef.current) {
      return;
    }

    topicRequestInFlightRef.current = true;
    setLoadingTopic(true);
    if (action) {
      setLoadingAction(action);
    }

    onUpdateSession((prev) => ({
      ...prev,
      status: "generating_topic",
      selectedTopicId: topicId,
      activeDepth: depth,
      activeAction: action,
      errorMessage: "",
      generationError: null,
    }));

    try {
      const result = await generateLearnTopic({
        documentIds: fullDocumentIds,
        topicId,
        topicTitle,
        parentTopicTitle,
        action,
        depth,
      });

      onUpdateSession((prev) => applyTopicResponse(prev, result));
    } catch (error) {
      onUpdateSession((prev) => ({
        ...prev,
        status: "error",
        errorMessage: error.message,
        generationError: error,
      }));
    } finally {
      topicRequestInFlightRef.current = false;
      setLoadingTopic(false);
      setLoadingAction(null);
    }
  }

  // Handle selecting a topic from the curriculum list
  function handleSelectTopic(topic) {
    onUpdateSession((prev) => ({
      ...prev,
      selectedTopicId: topic.id,
      selectedSubtopicId: null,
    }));

    loadTopicContent({
      topicId: topic.id,
      topicTitle: topic.title,
      depth: session.activeDepth || "standard",
      action: session.activeAction || null,
    });
  }

  // Handle selecting a subtopic
  function handleSelectSubtopic(parentTopic, subtopic) {
    onUpdateSession((prev) => ({
      ...prev,
      selectedTopicId: parentTopic.id,
      selectedSubtopicId: subtopic.id,
    }));

    loadTopicContent({
      topicId: subtopic.id,
      topicTitle: subtopic.title,
      parentTopicTitle: parentTopic.title,
      depth: session.activeDepth || "standard",
      action: session.activeAction || null,
    });
  }

  // Handle contextual action buttons (simplify, elaborate, example)
  function handleAction(actionId) {
    const activeTopic = findTopicById(session.outline, session.selectedTopicId);
    if (!activeTopic) return;

    let targetTopicId = activeTopic.id;
    let targetTopicTitle = activeTopic.title;
    let parentTitle = null;

    if (session.selectedSubtopicId) {
      const sub = findSubtopicById(activeTopic, session.selectedSubtopicId);
      if (sub) {
        targetTopicId = sub.id;
        targetTopicTitle = sub.title;
        parentTitle = activeTopic.title;
      }
    }

    loadTopicContent({
      topicId: targetTopicId,
      topicTitle: targetTopicTitle,
      parentTopicTitle: parentTitle,
      depth: session.activeDepth || "standard",
      action: actionId,
    });
  }

  // Reset to standard (un-modified) topic explanation
  function handleResetAction() {
    handleAction(null);
  }

  // Handle depth changes on active topic
  function handleDepthChange(newDepth) {
    const activeTopic = findTopicById(session.outline, session.selectedTopicId);
    if (!activeTopic) return;

    let targetTopicId = activeTopic.id;
    let targetTopicTitle = activeTopic.title;
    let parentTitle = null;

    if (session.selectedSubtopicId) {
      const sub = findSubtopicById(activeTopic, session.selectedSubtopicId);
      if (sub) {
        targetTopicId = sub.id;
        targetTopicTitle = sub.title;
        parentTitle = activeTopic.title;
      }
    }

    loadTopicContent({
      topicId: targetTopicId,
      topicTitle: targetTopicTitle,
      parentTopicTitle: parentTitle,
      depth: newDepth,
      action: session.activeAction || null,
    });
  }

  const isOutlineLoading = session.status === "generating_outline";
  const hasOutline = Boolean(session.outline);
  const isOutdated = isSelectionOutdated(session, fullDocumentIds);

  // Active topic resolution
  const activeTopic = hasOutline ? findTopicById(session.outline, session.selectedTopicId) : null;
  const activeSubtopic =
    activeTopic && session.selectedSubtopicId
      ? findSubtopicById(activeTopic, session.selectedSubtopicId)
      : null;

  const currentTopicTitle = activeSubtopic ? activeSubtopic.title : activeTopic?.title || "";
  const parentTopicTitle = activeSubtopic ? activeTopic?.title : null;
  const activeTopicContent = activeTopic
    ? getTopicContent(
        session,
        activeSubtopic ? activeSubtopic.id : activeTopic.id,
        session.activeDepth,
        session.activeAction
      )
    : null;

  return (
    <div className="space-y-5">
      {/* Error state & Guest limit notice */}
      {session.generationError && isGuestLimitError(session.generationError) ? (
        <GuestLimitNotice error={session.generationError} />
      ) : session.errorMessage ? (
        <div
          className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700"
          role="alert"
        >
          <div className="flex items-center justify-between gap-2">
            <span>{session.errorMessage}</span>
            <button
              type="button"
              onClick={() => onUpdateSession((prev) => ({ ...prev, errorMessage: "", generationError: null }))}
              className="text-red-500 hover:text-red-700 font-bold"
              aria-label="Dismiss error"
            >
              &times;
            </button>
          </div>
        </div>
      ) : null}

      {/* Selection change notice */}
      {hasOutline && isOutdated && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900 shadow-2xs"
          role="status"
        >
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 shrink-0 text-amber-600" aria-hidden="true">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
            </svg>
            <span>
              The selected documents for study have changed since this curriculum was created.
            </span>
          </div>
          <button
            type="button"
            disabled={isOutlineLoading || isNoneReadable}
            onClick={handleGenerateOutline}
            className="rounded bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white transition-colors hover:bg-amber-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:opacity-50"
          >
            Update Curriculum
          </button>
        </div>
      )}

      {/* Initial Hero / Uncut State */}
      {!hasOutline && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
          <div className="mx-auto max-w-xl text-center space-y-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-100 text-accent-700">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="h-6 w-6" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
              </svg>
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-900">Personalized Study Curriculum</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Learn Mode analyzes your selected documents to construct a structured curriculum with
                grounded explanations, key definitions, and source citations.
              </p>
            </div>

            {/* Initial Depth selector */}
            <div className="flex items-center justify-center gap-2 pt-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Curriculum Depth:
              </span>
              <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
                {LEARN_DEPTHS.map((depth) => (
                  <button
                    key={depth.id}
                    type="button"
                    disabled={isOutlineLoading}
                    onClick={() => setOutlineDepth(depth.id)}
                    className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                      outlineDepth === depth.id
                        ? "bg-white text-slate-900 shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {depth.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-3">
              <button
                type="button"
                disabled={isOutlineLoading || isNoneReadable}
                onClick={handleGenerateOutline}
                className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isOutlineLoading && (
                  <span
                    className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white"
                    aria-hidden="true"
                  />
                )}
                {isOutlineLoading ? "Generating curriculum..." : "Generate Curriculum"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Generating Outline Loading Skeleton */}
      {isOutlineLoading && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 animate-pulse">
          <div className="h-5 w-1/3 rounded bg-slate-200" />
          <div className="h-3.5 w-2/3 rounded bg-slate-100" />
          <div className="pt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="h-16 rounded-lg bg-slate-100" />
            <div className="h-16 rounded-lg bg-slate-100" />
          </div>
        </div>
      )}

      {/* Main Two-Column Curriculum & Topic Experience */}
      {hasOutline && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Column: Curriculum Topics */}
          <div className="lg:col-span-4 xl:col-span-4">
            <LearnCurriculum
              outline={session.outline}
              selectedTopicId={session.selectedTopicId}
              selectedSubtopicId={session.selectedSubtopicId}
              onSelectTopic={handleSelectTopic}
              onSelectSubtopic={handleSelectSubtopic}
              disabled={loadingTopic}
            />
          </div>

          {/* Right Column: Topic Deep Dive Viewer */}
          <div className="lg:col-span-8 xl:col-span-8">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <LearnTopicViewer
                topicTitle={currentTopicTitle}
                parentTopicTitle={parentTopicTitle}
                topicContent={activeTopicContent}
                activeAction={session.activeAction}
                activeDepth={session.activeDepth}
                onAction={handleAction}
                onResetAction={handleResetAction}
                onDepthChange={handleDepthChange}
                isLoading={loadingTopic}
                loadingAction={loadingAction}
                disabled={isOutlineLoading}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default LearnPanel;
