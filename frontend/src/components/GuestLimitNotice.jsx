import { useState } from "react";
import { isGuestLimitError } from "../api/errors.js";
import AuthPanel from "./AuthPanel";

/**
 * The one place every guest-limit rejection turns into UI (V3
 * Milestone 1 Phase 3) -- upload (UploadForm), AI generation
 * (SummaryPanel/FlashcardsPanel/QuizPanel/MindMapPanel), and chat
 * (ChatPanel) all catch the same shape of error (see api/errors.js's
 * GuestLimitError) and render this instead of their own plain error
 * text, so a guest sees the same message-plus-"Sign up" treatment no
 * matter which limit they hit, and each of those five panels stays a
 * one-line change ("show this instead of the plain error when
 * isGuestLimitError(error)") rather than re-implementing the same
 * banner five times.
 *
 * Opens AuthPanel in signup mode, with `error.message` (the exact
 * wording guest_limit_service.py already generated -- "Guests can
 * upload documents up to 3 times...") reused as the panel's intro
 * copy, only once the person actually clicks through -- nothing here
 * opens a modal on its own. That's deliberate: the brief is explicit
 * about not repeatedly interrupting someone with sign-in prompts, and
 * an inline banner the person can act on (or simply keep working
 * around) is a much lighter touch than a modal that appears the
 * moment a limit is hit.
 */
function GuestLimitNotice({ error }) {
  const [authPanelOpen, setAuthPanelOpen] = useState(false);

  if (!isGuestLimitError(error)) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-accent-200 bg-accent-50 px-3 py-2">
      <p className="text-sm text-accent-800">{error.message}</p>
      <button
        type="button"
        onClick={() => setAuthPanelOpen(true)}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-accent-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
      >
        Sign up
      </button>
      {authPanelOpen && (
        <AuthPanel onClose={() => setAuthPanelOpen(false)} initialMode="signup" introMessage={error.message} />
      )}
    </div>
  );
}

export default GuestLimitNotice;
