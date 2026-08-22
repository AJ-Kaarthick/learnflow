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

// Not every format has a page count — DOCX doesn't (pagination there
// depends on fonts/margins, not anything stored in the file), so
// `page_count` comes back null for it. Rather than leaving that slot
// in the metadata line blank, fall back to a file-type label derived
// from the extension itself (".docx" -> "DOCX") — same "derive from
// the filename, not a hardcoded format check" approach splitFilename
// below already uses, so any future page-count-less format falls back
// the same way with no extra code. Keeps this slot in the metadata
// line populated for every document, so the items after it (size,
// last opened) land in the same position regardless of format.
function formatPageCountOrFileType(doc) {
  const pageCount = formatPageCount(doc.page_count);
  if (pageCount) return pageCount;
  const extension = splitFilename(doc.original_filename).extension;
  return extension ? extension.slice(1).toUpperCase() : null;
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

function RenameIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
      <path
        d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DeleteIcon({ busy = false }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={`h-3.5 w-3.5 ${busy ? "animate-pulse" : ""}`}
      aria-hidden="true"
    >
      <path
        d="M6 7h12M9.5 7V5.25A1.25 1.25 0 0110.75 4h2.5A1.25 1.25 0 0114.5 5.25V7m2.25 0-.62 12.13A1.75 1.75 0 0114.38 21H9.62a1.75 1.75 0 01-1.75-1.87L7.25 7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DocumentList({
  documents,
  activeDocumentId,
  selectedDocumentIds,
  selectable = true,
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
        const pageOrType = formatPageCountOrFileType(doc);
        const fileSize = formatFileSize(doc.file_size_bytes);

        return (
          <li
            key={doc.id}
            className={`flex items-center gap-2 py-1.5 ${
              isActive ? "-mx-2 rounded-md bg-accent-50/50 px-2" : ""
            }`}
          >
            {!isEditing && selectable && (
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
                <>
                  <div className="flex min-w-0 items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onOpen(doc)}
                      title={doc.original_filename}
                      className="min-w-0 truncate rounded text-left text-sm font-medium text-slate-900 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
                    >
                      {doc.original_filename}
                    </button>
                    <span
                      className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${statusPillClasses(
                        doc.status
                      )}`}
                    >
                      {statusLabel(doc.status)}
                    </span>
                  </div>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11px] text-slate-400">
                    <span title="Upload date">{formatDate(doc.created_at)}</span>
                    {pageOrType && (
                      <span title={formatPageCount(doc.page_count) ? "Page count" : "File type"}>
                        &middot; {pageOrType}
                      </span>
                    )}
                    {fileSize && <span title="File size">&middot; {fileSize}</span>}
                    {doc.last_opened_at && (
                      <span title="Last opened">&middot; Opened {formatDate(doc.last_opened_at)}</span>
                    )}
                  </p>
                </>
              )}
            </div>

            {!isEditing && (
              <div className="flex shrink-0 items-center gap-0.5">
                <button
                  type="button"
                  onClick={() => startRename(doc)}
                  disabled={isBusy}
                  title="Rename"
                  aria-label={`Rename ${doc.original_filename}`}
                  className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <RenameIcon />
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(doc)}
                  disabled={isBusy}
                  title="Delete"
                  aria-label={`Delete ${doc.original_filename}`}
                  aria-busy={isBusy}
                  className="rounded p-1 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <DeleteIcon busy={isBusy} />
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
