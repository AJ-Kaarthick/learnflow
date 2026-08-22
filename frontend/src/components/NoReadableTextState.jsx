// Shown instead of the active Study panel (Summary/Flashcards/Quiz/
// Mind Map) when StudyWorkspace already knows — from the document's
// own character_count, see utils/documentReadiness.js — that there's
// nothing readable in it for the AI to work with. One shared
// component rather than a per-panel branch: all four tools need the
// exact same message (only the tool name changes), and rendering this
// in StudyWorkspace instead means the panels themselves are never
// even mounted, so there's no "Generate" button to click and no way
// to trigger a wasted (and, worse, fabricated-content) API call.
//
// Styling deliberately mirrors ChatPanel's own no-readable-text
// banner (same amber-200/amber-50/amber-700 border/background/body
// text) so the two correct treatments — the one Chat already had, and
// this one — look like the same feature rather than two different
// ones. amber-800 (the heading) previously had no dark-mode token
// override at all (see index.css's `.dark` block) — the actual bug
// behind "difficult to read against the dark UI" — which is fixed at
// the token level, not by avoiding the color here.
const TOOL_LABELS = {
  summary: "a summary",
  flashcards: "flashcards",
  quiz: "a quiz",
  mindmap: "a mind map",
};

function NoReadableTextState({ tool }) {
  const label = TOOL_LABELS[tool] ?? "study content";

  return (
    <div
      role="status"
      className="space-y-1.5 rounded-xl border border-amber-200 bg-amber-50 p-6 text-center"
    >
      <p className="text-sm font-semibold text-amber-800">No readable text detected</p>
      <p className="mx-auto max-w-md text-sm text-amber-700">
        LearnFlow couldn&apos;t find enough extractable text in this document to generate{" "}
        {label}. This usually means it&apos;s a scanned or image-only file. Try a document with
        selectable text instead.
      </p>
    </div>
  );
}

export default NoReadableTextState;
