// Shown in the Study Workspace (center panel) when no document is
// open. Milestone 1 left the center panel visually empty in this
// state — it's the largest region on the screen, so "empty" reads as
// unfinished rather than intentional. This version gives it a clear
// visual anchor and two concrete next steps instead of a blank area.
function EmptyWorkspaceState() {
  function focusUpload() {
    // The library's upload input (see UploadForm) has a stable id —
    // reusing it here rather than lifting upload state up through
    // WorkspaceShell just to open the native file picker from a
    // second place. Opens the same picker a click on that input
    // would, so "Upload a PDF" here is a real shortcut, not just copy
    // pointing at it.
    document.getElementById("pdf-upload")?.click();
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-10 text-center">
      <div
        className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-50 text-accent-600"
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7">
          <path
            d="M7 3.5h7.5L19 8v11a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 7 19V5a1.5 1.5 0 0 1 1.5-1.5Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M14 3.5V8h5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          <path
            d="M10 13.5h4M10 16.5h4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <div className="space-y-1.5">
        <p className="text-base font-semibold text-slate-900">No document open</p>
        <p className="max-w-xs text-sm text-slate-500">
          Your summary, flashcards, quiz, and mind map will show up here once you pick a
          document.
        </p>
      </div>

      <div className="flex flex-col items-center gap-2 text-sm">
        <p className="text-slate-600">
          <span className="font-medium text-slate-900">Select a document</span> from the library
          on the left
        </p>
        <p className="text-slate-400">or</p>
        <button
          type="button"
          onClick={focusUpload}
          className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
        >
          Upload a PDF
        </button>
      </div>
    </div>
  );
}

export default EmptyWorkspaceState;
