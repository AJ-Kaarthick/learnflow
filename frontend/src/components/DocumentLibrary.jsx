import { useEffect, useRef, useState } from "react";
import { listDocuments } from "../api/documents";
import DocumentList from "./DocumentList";

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
// api/documents.js), independently of whatever document HomePage
// currently has open. `refreshSignal` is bumped by the parent
// whenever something outside this component's control changes the
// underlying data (upload, rename, delete, open) so the list re-fetches.
function DocumentLibrary({
  refreshSignal,
  activeDocumentId,
  selectedDocumentIds,
  onOpen,
  onRename,
  onDelete,
  onToggleSelect,
}) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("uploaded_newest");
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const hasLoadedOnce = useRef(false);

  // Debounce the search box so typing doesn't fire a request per
  // keystroke, while still updating results live as the user types.
  useEffect(() => {
    const timeoutId = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeoutId);
  }, [searchInput]);

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

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">
          Document Library
        </h2>
        {!showInitialLoading && (
          <span className="shrink-0 text-xs text-slate-400">
            {resultCountLabel(documents.length, search)}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-400">
        Check the box next to a document to include it in the chat below. Select more than one
        to chat across several documents at once.
      </p>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search by filename..."
          aria-label="Search documents by filename"
          className="w-full flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        />
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          aria-label="Sort documents"
          className="shrink-0 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="h-80 overflow-y-auto rounded-md border border-slate-100">
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
                <p className="text-xs text-slate-400">Upload a PDF below to get started.</p>
              </>
            )}
          </div>
        ) : (
          <div className="px-3">
            <DocumentList
              documents={documents}
              activeDocumentId={activeDocumentId}
              selectedDocumentIds={selectedDocumentIds}
              onOpen={onOpen}
              onRename={onRename}
              onDelete={onDelete}
              onToggleSelect={onToggleSelect}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default DocumentLibrary;
