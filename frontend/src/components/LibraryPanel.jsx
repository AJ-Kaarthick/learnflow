import { useEffect, useRef, useState } from "react";
import { listDocuments } from "../api/documents";
import DocumentList from "./DocumentList";
import UploadForm from "./UploadForm";
import {
  loadLibraryFilters,
  loadLibraryScrollTop,
  saveLibraryFilters,
  saveLibraryScrollTop,
} from "../utils/persistence";
import { FOCUS_SEARCH_EVENT } from "../utils/shortcutEvents";

// How long to wait after the user stops scrolling before saving the
// new position — scroll events fire continuously while scrolling, so
// writing to storage on every one would be wasteful.
const SCROLL_SAVE_DEBOUNCE_MS = 200;

const SORT_OPTIONS = [
  { value: "uploaded_newest", label: "Upload Date (Newest First)" },
  { value: "uploaded_oldest", label: "Upload Date (Oldest First)" },
  { value: "name_asc", label: "Name (A–Z)" },
  { value: "name_desc", label: "Name (Z–A)" },
  { value: "recently_opened", label: "Recently Opened" },
];

const SEARCH_DEBOUNCE_MS = 200;

function resultCountLabel(count, search) {
  const noun = count === 1 ? "document" : "documents";
  if (!search) return `${count} ${noun}`;
  const resultNoun = count === 1 ? "result" : "results";
  return `${count} ${resultNoun} for "${search}"`;
}

// The Document Library panel: owns search/sort state and fetches its
// own data (search and sort are both server-side, see
// api/documents.js), independently of whatever document the current
// page has open. `refreshSignal` is bumped by the parent whenever
// something outside this component's control changes the underlying
// data (upload, rename, delete, open) so the list re-fetches.
//
// V2.4 Milestone 1: this panel is now reused on two different pages
// with two different selection models — Study just opens a document
// (no chat-style multi-select), Chat selects one or more documents to
// converse with. `selectable` switches between them: `false` hides
// the per-row checkbox column and the "check its box..." helper line
// entirely, so Study's library doesn't show chat affordances for a
// page that no longer has a chat panel. Defaults to `true` (the
// original, chat-selection behavior) so existing callers don't need
// to change.
function LibraryPanel({
  refreshSignal,
  activeDocumentId,
  selectedDocumentIds = [],
  selectable = true,
  onOpen,
  onRename,
  onDelete,
  onToggleSelect,
  onUploadComplete,
}) {
  // Search and sort both restore from last session (V2.1 Milestone 2,
  // features 7 & 8) — read once via lazy initializers so the very
  // first fetch below (in the [search, sort, refreshSignal] effect)
  // already requests the previously filtered/sorted results, rather
  // than fetching the default view and then re-fetching a moment
  // later.
  const [searchInput, setSearchInput] = useState(() => loadLibraryFilters().search);
  const [search, setSearch] = useState(() => loadLibraryFilters().search);
  const [sort, setSort] = useState(() => loadLibraryFilters().sort);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const hasLoadedOnce = useRef(false);

  // The scrollable results list — restoring/saving scroll position
  // (feature 9) is applied directly to this element.
  const scrollContainerRef = useRef(null);
  const hasRestoredScrollRef = useRef(false);
  const scrollSaveTimeoutRef = useRef(null);

  // Target of the Ctrl/Cmd+K shortcut (Milestone 4) — see AppShell
  // for where that's caught and dispatched.
  const searchInputRef = useRef(null);

  useEffect(() => {
    function handleFocusSearch() {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    }
    window.addEventListener(FOCUS_SEARCH_EVENT, handleFocusSearch);
    return () => window.removeEventListener(FOCUS_SEARCH_EVENT, handleFocusSearch);
  }, []);

  // Debounce the search box so typing doesn't fire a request per
  // keystroke, while still updating results live as the user types.
  useEffect(() => {
    const timeoutId = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeoutId);
  }, [searchInput]);

  // Persist search/sort together whenever the *debounced* search
  // settles or sort changes — not on every keystroke, same cadence as
  // the fetch effect below so a save never lags behind what's on
  // screen.
  useEffect(() => {
    saveLibraryFilters({ search, sort });
  }, [search, sort]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listDocuments({ search, sort })
      .then((list) => {
        if (cancelled) return;
        setDocuments(list);
      })
      .catch(() => {
        // Leave the list as-is; the panel just shows whatever it had.
      })
      .finally(() => {
        if (cancelled) return;
        hasLoadedOnce.current = true;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, sort, refreshSignal]);

  const showInitialLoading = loading && !hasLoadedOnce.current;
  const isSearchActive = search.length > 0;

  // Restores the saved scroll position once, right after the results
  // list first finishes loading (restoring any earlier — while the
  // list is still empty/showing a loading state — would have nothing
  // to scroll). Only ever runs this once per mount; later re-fetches
  // (new search, new sort, a refresh elsewhere) intentionally don't
  // re-trigger it; a new search producing a shorter list, for
  // instance, should just show its own top, not fight to reapply an
  // old scroll offset that may no longer make sense for it.
  useEffect(() => {
    if (hasRestoredScrollRef.current || showInitialLoading) return;
    hasRestoredScrollRef.current = true;
    const savedScrollTop = loadLibraryScrollTop();
    if (savedScrollTop > 0 && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = savedScrollTop;
    }
  }, [showInitialLoading]);

  function handleResultsScroll(event) {
    const scrollTop = event.currentTarget.scrollTop;
    if (scrollSaveTimeoutRef.current) clearTimeout(scrollSaveTimeoutRef.current);
    scrollSaveTimeoutRef.current = setTimeout(
      () => saveLibraryScrollTop(scrollTop),
      SCROLL_SAVE_DEBOUNCE_MS
    );
  }

  useEffect(() => {
    return () => {
      if (scrollSaveTimeoutRef.current) clearTimeout(scrollSaveTimeoutRef.current);
    };
  }, []);

  return (
    <div className="flex h-full min-w-0 flex-col gap-5">
      {/* Upload used to sit at the bottom of this panel, below a list
          that can get long — effectively invisible once a handful of
          documents exist. It's the first thing in the column now,
          styled as a clear, self-contained action rather than a form
          tacked onto the end of the list. */}
      <div className="shrink-0 rounded-lg border border-dashed border-slate-300 bg-surface p-4">
        <UploadForm onUploadComplete={onUploadComplete} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 border-t border-slate-200 pt-5 lg:overflow-hidden">
        <div className="flex shrink-0 items-center justify-between gap-3">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">
            Document Library
          </h2>
          {!showInitialLoading && (
            <span className="shrink-0 text-xs text-slate-400">
              {resultCountLabel(documents.length, search)}
            </span>
          )}
        </div>

        <p className="shrink-0 text-xs text-slate-400">
          {selectable
            ? "Click a document to open it. Check its box to include it in the chat — check more than one to chat across several documents at once."
            : "Click a document to open it in your study workspace."}
        </p>

        {/* Stacked unconditionally, not `sm:flex-row` — `sm:` reacts
            to the viewport, not this column's actual width, so on any
            desktop-width screen it was forcing the search input and
            sort dropdown onto one row inside a ~260–360px sidebar,
            squeezing the input down to a few visible characters
            ("Sea..."). This column is narrow at every screen size it
            appears at, so it should always stack. `min-w-0` on the
            input guards against the same class of overflow even if
            that ever changes. */}
        <div className="flex shrink-0 flex-col gap-2">
          <input
            ref={searchInputRef}
            type="text"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search by filename..."
            aria-label="Search documents by filename"
            className="w-full min-w-0 rounded-md border border-slate-300 bg-surface px-3 py-1.5 text-sm text-slate-900 caret-accent-600 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          />
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value)}
            aria-label="Sort documents"
            className="w-full min-w-0 rounded-md border border-slate-300 bg-surface px-2 py-1.5 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div
          ref={scrollContainerRef}
          onScroll={handleResultsScroll}
          className="min-h-0 flex-1 overflow-y-auto rounded-md border border-slate-100 bg-surface lg:mt-1"
        >
          {showInitialLoading ? (
            <p className="p-4 text-sm text-slate-500">Loading documents...</p>
          ) : documents.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
              {isSearchActive ? (
                <>
                  <p className="text-sm font-medium text-slate-700">
                    No documents match &quot;{search}&quot;
                  </p>
                  <p className="text-xs text-slate-400">Try a different search term.</p>
                  <button
                    type="button"
                    onClick={() => setSearchInput("")}
                    className="mt-2 text-xs font-medium text-accent-700 hover:text-accent-800"
                  >
                    Clear search
                  </button>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-slate-700">No documents yet</p>
                  <p className="text-xs text-slate-400">Upload a PDF, DOCX, PPTX, PNG, or JPG above to get started.</p>
                </>
              )}
            </div>
          ) : (
            <div className="px-3">
              <DocumentList
                documents={documents}
                activeDocumentId={activeDocumentId}
                selectedDocumentIds={selectedDocumentIds}
                selectable={selectable}
                onOpen={onOpen}
                onRename={onRename}
                onDelete={onDelete}
                onToggleSelect={onToggleSelect}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LibraryPanel;
