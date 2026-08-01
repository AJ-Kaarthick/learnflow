import { useState } from "react";

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// File sizes come back from the API in bytes. KB is the smallest unit
// shown (a sub-KB PDF is vanishingly rare) so the number stays short
// and glanceable in a compact metadata line.
function formatFileSize(bytes) {
  if (bytes === null || bytes === undefined) return null;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.max(1, Math.round(kb))} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatPageCount(pageCount) {
  if (pageCount === null || pageCount === undefined) return null;
  return `${pageCount} ${pageCount === 1 ? "page" : "pages"}`;
}

function statusPillClasses(status) {
  if (status === "ready") return "bg-emerald-50 text-emerald-700";
  if (status === "failed") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}

function statusLabel(status) {
  if (status === "ready") return "Ready";
  if (status === "failed") return "Failed";
  return status;
}

// Splits a filename into its base name and extension (dot included,
// e.g. ".pdf", ".docx", ".png"), the same way the backend does —
// derived from the filename itself, not a hardcoded file type, so
// this keeps working as LearnFlow adds support for more of them.
// A leading dot with nothing before it (e.g. ".pdf" alone) doesn't
// count as an extension, it's just a name.
function splitFilename(filename) {
  const lastDot = filename.lastIndexOf(".");
  if (lastDot <= 0) {
    return { base: filename, extension: "" };
  }
  return { base: filename.slice(0, lastDot), extension: filename.slice(lastDot) };
}

function DocumentList({
  documents,
  activeDocumentId,
  selectedDocumentIds,
  onOpen,
  onRename,
  onDelete,
  onToggleSelect,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [editError, setEditError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  function startRename(doc) {
    setEditingId(doc.id);
    setEditValue(splitFilename(doc.original_filename).base);
    setEditError(null);
  }

  function cancelRename() {
    setEditingId(null);
    setEditValue("");
    setEditError(null);
  }

  async function saveRename(doc) {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === splitFilename(doc.original_filename).base) {
      cancelRename();
      return;
    }
    setBusyId(doc.id);
    setEditError(null);
    try {
      // Send just the base name — the backend reapplies this
      // document's real extension server-side, so it can never be
      // edited away here regardless of file type. The backend also
      // validates the name (not blank, not punctuation-only, not a
      // duplicate) — on failure, keep editing open and show why.
      await onRename(doc.id, trimmed);
      cancelRename();
    } catch (error) {
      setEditError(error.message || "Couldn't rename this document.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(doc) {
    const confirmed = window.confirm(`Delete "${doc.original_filename}"? This can't be undone.`);
    if (!confirmed) return;
    setBusyId(doc.id);
    try {
      await onDelete(doc.id);
    } finally {
      setBusyId(null);
    }
  }

  if (documents.length === 0) {
    return null;
  }

  return (
    <ul className="divide-y divide-slate-100">
      {documents.map((doc) => {
        const isEditing = editingId === doc.id;
        const isActive = doc.id === activeDocumentId;
        const isBusy = busyId === doc.id;
        const isSelected = selectedDocumentIds.includes(doc.id);
        const canSelect = doc.status === "ready";

        return (
          <li
            key={doc.id}
            className={`flex items-center justify-between gap-3 py-2.5 ${
              isActive ? "-mx-2 rounded-md bg-accent-50/50 px-2" : ""
            }`}
          >
            {!isEditing && (
              <input
                type="checkbox"
                checked={isSelected}
                disabled={!canSelect}
                onChange={() => onToggleSelect(doc)}
                title={
                  canSelect
                    ? `Include "${doc.original_filename}" in chat`
                    : "Only ready documents can be included in chat"
                }
                aria-label={`Include ${doc.original_filename} in chat`}
                className="h-4 w-4 shrink-0 rounded border-slate-300 text-accent-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
              />
            )}
            <div className="min-w-0 flex-1">
              {isEditing ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="flex min-w-0 flex-1 items-center gap-1 rounded-md border border-slate-300 bg-surface px-2 transition-colors focus-within:border-accent-500 focus-within:ring-2 focus-within:ring-inset focus-within:ring-accent-500">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(event) => {
                          setEditValue(event.target.value);
                          setEditError(null);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") saveRename(doc);
                          if (event.key === "Escape") cancelRename();
                        }}
                        autoFocus
                        className="min-w-0 flex-1 bg-transparent py-1.5 text-sm text-slate-900 caret-accent-600 outline-none placeholder:text-slate-400"
                      />
                      {splitFilename(doc.original_filename).extension && (
                        <span
                          title="The file type can't be changed"
                          className="shrink-0 select-none text-sm text-slate-400"
                        >
                          {splitFilename(doc.original_filename).extension}
                        </span>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <button
                        onClick={() => saveRename(doc)}
                        disabled={isBusy}
                        className="rounded-md bg-accent-600 px-2.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Save
                      </button>
                      <button
                        onClick={cancelRename}
                        disabled={isBusy}
                        className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                  {editError ? (
                    <p role="alert" className="pl-2 text-[11px] font-medium text-red-600">
                      {editError}
                    </p>
                  ) : (
                    splitFilename(doc.original_filename).extension && (
                      <p className="pl-2 text-[11px] text-slate-400">File type can&apos;t be changed</p>
                    )
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onOpen(doc)}
                  title={doc.original_filename}
                  className="block w-full truncate rounded text-left text-sm font-medium text-slate-900 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
                >
                  {doc.original_filename}
                </button>
              )}

              {!isEditing && (
                <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-400">
                  <span
                    className={`rounded-full px-1.5 py-0.5 font-medium ${statusPillClasses(
                      doc.status
                    )}`}
                  >
                    {statusLabel(doc.status)}
                  </span>
                  <span title="Upload date">{formatDate(doc.created_at)}</span>
                  {formatPageCount(doc.page_count) && (
                    <span title="Page count">
                      &middot; {formatPageCount(doc.page_count)}
                    </span>
                  )}
                  {formatFileSize(doc.file_size_bytes) && (
                    <span title="File size">
                      &middot; {formatFileSize(doc.file_size_bytes)}
                    </span>
                  )}
                  {doc.last_opened_at && (
                    <span title="Last opened">
                      &middot; Opened {formatDate(doc.last_opened_at)}
                    </span>
                  )}
                </p>
              )}
            </div>

            {!isEditing && (
              <div className="flex shrink-0 items-center gap-3">
                <button
                  type="button"
                  onClick={() => startRename(doc)}
                  disabled={isBusy}
                  className="rounded text-xs font-medium text-slate-500 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(doc)}
                  disabled={isBusy}
                  className="rounded text-xs font-medium text-slate-500 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
                >
                  {isBusy ? "..." : "Delete"}
                </button>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default DocumentList;
