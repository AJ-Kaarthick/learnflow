import { useEffect, useState } from "react";
import { listDocuments } from "../api/documents.js";
import AuthPanel from "../components/AuthPanel.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { ROUTES, routeHref } from "../router/useHashRoute.js";
import {
  QUICK_ACTIONS,
  formatGreetingTitle,
  formatRecentDocumentDate,
  getGreetingSubtitle,
} from "../utils/homeState.js";
import { saveActiveDocumentId } from "../utils/persistence.js";

const RECENT_DOCUMENT_LIMIT = 5;

/**
 * LearnFlow Home Dashboard (V3 Milestone 6 Phase 1).
 *
 * Provides:
 * 1. Personalized, identity-aware greeting banner.
 * 2. Non-intrusive guest session callout with one-click access to AuthPanel.
 * 3. 4-way Workspace Quick Actions grid (Study, Revision, Chat, Progress).
 * 4. Preserved 'Continue studying' list for recently opened documents.
 */
function HomePage() {
  const { identity, isAuthenticated, status: authStatus } = useAuth();
  const [authPanelOpen, setAuthPanelOpen] = useState(false);
  const [authPanelMode, setAuthPanelMode] = useState("signup");

  const [recentDocuments, setRecentDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  useEffect(() => {
    let cancelled = false;

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
  }, []);

  function handleContinueStudying(doc) {
    saveActiveDocumentId(doc.id);
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
