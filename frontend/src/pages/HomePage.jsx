import { useEffect, useState } from "react";
import { listDocuments } from "../api/documents";
import { ROUTES, routeHref } from "../router/useHashRoute";
import { saveActiveDocumentId } from "../utils/persistence";

// How many recently-opened documents "Continue studying" shows — a
// short, glanceable list, not a full second copy of the library
// (that's what Study's own LibraryPanel is for).
const RECENT_DOCUMENT_LIMIT = 5;

// Same "absolute date, no external date library" approach DocumentList
// and StudyWorkspace already use for their own metadata lines — kept
// local to this file rather than extracted, since this is the third
// near-identical copy and unifying all three is a cleanup outside
// this milestone's scope (see the brief: smallest clean change that
// establishes the new page structure).
function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// V2.4 Milestone 1: foundation for a future Home/Dashboard page.
// Deliberately lightweight per the brief — a landing experience, entry
// points to Study and Chat, and a "continue studying" list built
// entirely from data the documents API already returns
// (`last_opened_at`, via the existing `recently_opened` sort). No new
// backend endpoint, no mastery/revision dashboard (that's explicitly a
// later milestone) — just enough that arriving at LearnFlow lands
// somewhere purposeful instead of straight into one particular tool.
function HomePage() {
  const [recentDocuments, setRecentDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listDocuments({ sort: "recently_opened" })
      .then((documents) => {
        if (cancelled) return;
        // "recently_opened" sorts documents that have never been
        // opened to the back rather than excluding them — filter
        // those out here so a fresh library with only unopened
        // uploads correctly shows the empty state below, not a list
        // of documents nobody has actually studied yet.
        setRecentDocuments(
          documents.filter((doc) => doc.last_opened_at).slice(0, RECENT_DOCUMENT_LIMIT)
        );
      })
      .catch(() => {
        // Leave the list empty; the empty state below is still a
        // fully working fallback.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Hands off to Study's own restore-on-mount (see StudyPage) by
  // setting the same `activeDocumentId` it already reads from — no
  // document-loading logic duplicated here, just the one piece of
  // shared, persisted state that means "this is the active study
  // document."
  function continueStudying(doc) {
    saveActiveDocumentId(doc.id);
  }

  return (
    <main aria-label="Home" className="min-w-0 flex-1 overflow-y-auto p-6 lg:p-10">
      <div className="mx-auto max-w-4xl space-y-10">
        <div className="space-y-1.5">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Welcome back</h1>
          <p className="text-sm text-slate-500">
            Pick up where you left off, or head into Study or Chat with your documents.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <a
            href={routeHref(ROUTES.STUDY)}
            className="group rounded-xl border border-slate-200 bg-surface p-5 transition-colors hover:border-accent-300 hover:bg-accent-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            <p className="text-base font-semibold text-slate-900 group-hover:text-accent-700">Study</p>
            <p className="mt-1 text-sm text-slate-500">
              Summaries, flashcards, quizzes, and mind maps for your documents.
            </p>
          </a>
          <a
            href={routeHref(ROUTES.CHAT)}
            className="group rounded-xl border border-slate-200 bg-surface p-5 transition-colors hover:border-accent-300 hover:bg-accent-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            <p className="text-base font-semibold text-slate-900 group-hover:text-accent-700">Chat</p>
            <p className="mt-1 text-sm text-slate-500">
              Ask questions grounded in one document, or several at once.
            </p>
          </a>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">Continue studying</h2>
            {/* V2.4 Milestone 1 UX polish (issue 3): Home's own list is
                deliberately short (RECENT_DOCUMENT_LIMIT) and shows
                only what's already been opened — it's not a second
                document library, and isn't meant to grow into one.
                This is the way out to the real one: Study's
                LibraryPanel already has full search/sort/upload/
                rename/delete, so the fix for "I can't find document X
                in this short list" is a link there, not adding any of
                that here. */}
            <a
              href={routeHref(ROUTES.STUDY)}
              className="shrink-0 text-sm font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
            >
              View all documents →
            </a>
          </div>

          {loading ? (
            <p className="text-sm text-slate-500">Loading...</p>
          ) : recentDocuments.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center">
              <p className="text-sm font-medium text-slate-700">Nothing opened yet</p>
              <p className="mt-1 text-sm text-slate-400">
                Head to{" "}
                <a href={routeHref(ROUTES.STUDY)} className="font-medium text-accent-700 hover:text-accent-800">
                  Study
                </a>{" "}
                to upload your first document.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-surface">
              {recentDocuments.map((doc) => (
                <li key={doc.id}>
                  <a
                    href={routeHref(ROUTES.STUDY)}
                    onClick={() => continueStudying(doc)}
                    className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
                  >
                    <span className="min-w-0 truncate text-sm font-medium text-slate-800">
                      {doc.original_filename}
                    </span>
                    <span className="shrink-0 text-xs text-slate-400">
                      Opened {formatDate(doc.last_opened_at)}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}

export default HomePage;
