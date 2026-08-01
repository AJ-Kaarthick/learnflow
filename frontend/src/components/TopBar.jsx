import { useState } from "react";
import BackendStatus from "./BackendStatus";
import SettingsPanel from "./SettingsPanel";

// Persistent top bar for the workspace. Carries the title and
// subtitle that previously lived in HomePage's <header>, plus
// BackendStatus (previously shown further down the page, next to the
// upload form) — both are app-wide, not specific to the library
// section they used to sit in, so they've moved up to the one place
// that's visible regardless of which panel the user is looking at.
//
// V2.1 Milestone 3 adds the Settings entry point here too, for the
// same reason: personalization is app-wide, so its trigger belongs
// in the one chrome element visible no matter which document or
// study tool is open.
function TopBar() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-surface px-4 py-3 sm:px-6 lg:px-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Learn<span className="text-accent-600">Flow</span>
        </h1>
        <p className="text-xs text-slate-500">
          Pick up where you left off, or upload a new PDF.
        </p>
      </div>
      <div className="flex items-center gap-4">
        <BackendStatus />
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M11.078 2.25c-.917 0-1.699.663-1.85 1.567L9.05 4.889c-.02.12-.115.26-.297.348a7.493 7.493 0 0 0-.986.57c-.166.115-.334.126-.45.083L5.907 5.5a1.875 1.875 0 0 0-2.282.819l-.922 1.597a1.875 1.875 0 0 0 .432 2.385l.84.692c.095.078.17.229.154.43a7.598 7.598 0 0 0 0 1.139c.015.2-.059.352-.153.43l-.841.692a1.875 1.875 0 0 0-.432 2.385l.922 1.597a1.875 1.875 0 0 0 2.282.818l1.19-.416c.196-.077.318.043.45.107.301.184.639.409.986.57.183.088.278.228.297.349l.194 1.226c.121.885.897 1.548 1.837 1.548h1.844c.938 0 1.716-.663 1.837-1.548l.194-1.226c.02-.12.115-.26.297-.349a7.5 7.5 0 0 0 .986-.57c.166-.115.334-.126.45-.083l1.192.416c.895.313 1.917-.09 2.284-.818l.922-1.597a1.875 1.875 0 0 0-.432-2.385l-.84-.692c-.095-.078-.17-.229-.154-.43a7.598 7.598 0 0 0 0-1.139c-.015-.2.059-.352.153-.43l.841-.692c.708-.582.891-1.59.432-2.385l-.922-1.597a1.875 1.875 0 0 0-2.282-.818l-1.19.416c-.196.077-.318-.043-.45-.107a7.5 7.5 0 0 0-.986-.57c-.183-.088-.278-.228-.297-.349l-.194-1.226A1.875 1.875 0 0 0 12.921 2.25h-1.843ZM12 15.75a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5Z"
              clipRule="evenodd"
            />
          </svg>
          Settings
        </button>
      </div>
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
    </header>
  );
}

export default TopBar;
