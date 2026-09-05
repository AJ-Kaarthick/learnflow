import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import AppNav from "./AppNav";
import AuthPanel from "./AuthPanel";
import BackendStatus from "./BackendStatus";
import SettingsPanel from "./SettingsPanel";

// V3 Milestone 1 Phase 2: the minimal account-authentication control
// -- "Sign in" for a guest, or the account's email plus "Log out" for
// an authenticated user. Lives in TopBar for the same reason Settings
// already does (see this file's existing comment below): authentication
// state, like personalization, is app-wide chrome, not specific to
// any one page. Nothing renders here at all while identity is still
// loading (the brief moment before the first GET /identity/me
// resolves), rather than flashing a "Sign in" button that would
// immediately be replaced.
function AuthControl() {
  const { status, isAuthenticated, identity, logout } = useAuth();
  const [authPanelOpen, setAuthPanelOpen] = useState(false);

  if (status === "loading") return null;

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden text-sm text-slate-600 sm:inline" title={identity.email}>
          {identity.email}
        </span>
        <button
          type="button"
          onClick={() => logout()}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
        >
          Log out
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setAuthPanelOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
      >
        Sign in
      </button>
      {authPanelOpen && <AuthPanel onClose={() => setAuthPanelOpen(false)} />}
    </>
  );
}

// Persistent top bar for the app. Carries the title that previously
// lived in HomePage's <header>, plus BackendStatus (previously shown
// further down the page, next to the upload form) — both are
// app-wide, not specific to any one panel, so they live in the one
// piece of chrome visible no matter which page is showing.
//
// V2.1 Milestone 3 added the Settings entry point here for the same
// reason: personalization is app-wide. V2.4 Milestone 1 adds the
// top-level page nav (see AppNav) here too — LearnFlow's move from a
// single workspace to Home/Study/Chat/... pages makes "where am I,
// where can I go" an app-wide chrome concern the same way Settings
// already was, not something that belongs inside any one page.
function TopBar({ route, onOpenShortcuts }) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-surface px-4 py-3 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <h1 className="shrink-0 text-2xl font-bold tracking-tight text-slate-900">
          Learn<span className="text-accent-600">Flow</span>
        </h1>
        <AppNav route={route} />
      </div>
      <div className="flex items-center gap-4">
        <BackendStatus />
        <AuthControl />
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
      {settingsOpen && (
        <SettingsPanel onClose={() => setSettingsOpen(false)} onOpenShortcuts={onOpenShortcuts} />
      )}
    </header>
  );
}

export default TopBar;
