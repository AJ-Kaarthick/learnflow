import { useState } from "react";

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
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

function DocumentList({ documents, activeDocumentId, onOpen, onRename, onDelete }) {
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [busyId, setBusyId] = useState(null);

  function startRename(doc) {
    setEditingId(doc.id);
    setEditValue(splitFilename(doc.original_filename).base);
  }

  function cancelRename() {
    setEditingId(null);
    setEditValue("");
  }

  async function saveRename(doc) {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === splitFilename(doc.original_filename).base) {
      cancelRename();
      return;
    }
    setBusyId(doc.id);
    try {
      // Send just the base name — the backend reapplies this
      // document's real extension server-side, so it can never be
      // edited away here regardless of file type.
      await onRename(doc.id, trimmed);
    } finally {
      setBusyId(null);
      cancelRename();
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
    return <p className="text-sm text-slate-500">No documents uploaded yet.</p>;
  }

  return (
    <ul className="divide-y divide-slate-100">
      {documents.map((doc) => {
        const isEditing = editingId === doc.id;
        const isActive = doc.id === activeDocumentId;
        const isBusy = busyId === doc.id;

        return (
          <li
            key={doc.id}
            className={`flex items-center justify-between gap-3 py-2.5 ${
              isActive ? "-mx-2 rounded-md bg-accent-50/50 px-2" : ""
            }`}
          >
            <div className="min-w-0 flex-1">
              {isEditing ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="flex min-w-0 flex-1 items-center rounded-md border border-slate-300 bg-white pr-2 focus-within:ring-2 focus-within:ring-accent-500">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(event) => setEditValue(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") saveRename(doc);
                          if (event.key === "Escape") cancelRename();
                        }}
                        autoFocus
                        className="w-full min-w-0 flex-1 rounded-md border-0 px-2 py-1 text-sm focus-visible:outline-none"
                      />
                      {splitFilename(doc.original_filename).extension && (
                        <span
                          title="The file type can't be changed"
                          className="shrink-0 select-none text-sm text-slate-400"
                        >
                          {splitFilename(doc.original_filename).extension}
                        </span>
                      )}
                    </span>
                    <button
                      onClick={() => saveRename(doc)}
                      disabled={isBusy}
                      className="text-xs font-medium text-accent-700 hover:text-accent-800 disabled:opacity-40"
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelRename}
                      disabled={isBusy}
                      className="text-xs font-medium text-slate-500 hover:text-slate-700 disabled:opacity-40"
                    >
                      Cancel
                    </button>
                  </div>
                  {splitFilename(doc.original_filename).extension && (
                    <p className="pl-2 text-[11px] text-slate-400">File type can&apos;t be changed</p>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onOpen(doc)}
                  title={doc.original_filename}
                  className="block w-full truncate rounded text-left text-sm font-medium text-slate-900 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  {doc.original_filename}
                </button>
              )}

              {!isEditing && (
                <p className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                  <span
                    className={`rounded-full px-1.5 py-0.5 font-medium ${statusPillClasses(
                      doc.status
                    )}`}
                  >
                    {statusLabel(doc.status)}
                  </span>
                  {formatDate(doc.created_at)}
                </p>
              )}
            </div>

            {!isEditing && (
              <div className="flex shrink-0 items-center gap-3">
                <button
                  type="button"
                  onClick={() => startRename(doc)}
                  disabled={isBusy}
                  className="rounded text-xs font-medium text-slate-500 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-40"
                >
                  Rename
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(doc)}
                  disabled={isBusy}
                  className="rounded text-xs font-medium text-slate-500 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-40"
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
