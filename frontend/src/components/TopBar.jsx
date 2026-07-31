import BackendStatus from "./BackendStatus";

// Persistent top bar for the workspace. Carries the title and
// subtitle that previously lived in HomePage's <header>, plus
// BackendStatus (previously shown further down the page, next to the
// upload form) — both are app-wide, not specific to the library
// section they used to sit in, so they've moved up to the one place
// that's visible regardless of which panel the user is looking at.
function TopBar() {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:px-6 lg:px-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Learn<span className="text-accent-600">Flow</span>
        </h1>
        <p className="text-xs text-slate-500">
          Pick up where you left off, or upload a new PDF.
        </p>
      </div>
      <BackendStatus />
    </header>
  );
}

export default TopBar;
