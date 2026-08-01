import { useEffect, useRef } from "react";
import {
  ACCENT_OPTIONS,
  ANIMATION_OPTIONS,
  DENSITY_OPTIONS,
  THEME_OPTIONS,
  usePersonalization,
} from "../context/PersonalizationContext";

const ACCENT_SWATCH_CLASSES = {
  blue: "bg-[#2563eb]",
  purple: "bg-[#7c3aed]",
  green: "bg-[#16a34a]",
  orange: "bg-[#ea580c]",
};

const ACCENT_LABELS = { blue: "Blue", purple: "Purple", green: "Green", orange: "Orange" };
const THEME_LABELS = { light: "Light", dark: "Dark", system: "System" };
const DENSITY_LABELS = { comfortable: "Comfortable", compact: "Compact" };
const DENSITY_DESCRIPTIONS = {
  comfortable: "Relaxed spacing, the default layout.",
  compact: "Tighter padding so more fits on screen.",
};

// A row of mutually-exclusive buttons standing in for a radio group.
// Plain <button>s (not native radio inputs) so they can carry the
// app's existing focus-visible/accent styling, with role="radio" +
// aria-checked so assistive tech still announces them as a group of
// choices rather than a handful of unrelated buttons.
function SegmentedControl({ legend, options, value, onChange, renderOption }) {
  return (
    <div>
      <span className="block text-xs font-medium text-slate-500" id={`${legend}-label`}>
        {legend}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={`${legend}-label`}
        className="mt-2 flex flex-wrap gap-2"
      >
        {options.map((option) => {
          const isActive = option === value;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => onChange(option)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset ${
                isActive
                  ? "border-accent-600 bg-accent-600 text-white"
                  : "border-slate-300 text-slate-700 hover:bg-slate-50"
              }`}
            >
              {renderOption ? renderOption(option, isActive) : option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SettingsSection({ title, children }) {
  return (
    <section className="space-y-4">
      <h3 className="text-sm font-semibold tracking-tight text-slate-900">{title}</h3>
      {children}
    </section>
  );
}

// The Settings dialog: Appearance (theme, accent), Workspace (density,
// animations), and About. A single dedicated panel per the brief,
// rather than each preference having its own popover — everything
// personalization-related lives in one predictable place. All state
// reads/writes go through usePersonalization(), which is itself the
// only thing that touches storage/documentElement (see
// PersonalizationContext) — this component only ever calls its
// setters.
function SettingsPanel({ onClose }) {
  const { theme, accent, density, animations, setTheme, setAccent, setDensity, setAnimations } =
    usePersonalization();

  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  // Focus the dialog on open, close on Escape, and trap Tab within it
  // — a modal dialog shouldn't let keyboard focus leak out to the
  // workspace behind it while it's open.
  useEffect(() => {
    closeButtonRef.current?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = dialogRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    // Prevents the workspace behind the dialog from scrolling while
    // it's open, same reasoning as WorkspaceShell locking the page to
    // one scroll container at a time.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-surface shadow-xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 id="settings-title" className="text-base font-semibold tracking-tight text-slate-900">
            Settings
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-8 overflow-y-auto px-5 py-5">
          <SettingsSection title="Appearance">
            <SegmentedControl
              legend="Theme"
              options={THEME_OPTIONS}
              value={theme}
              onChange={setTheme}
              renderOption={(option) => THEME_LABELS[option]}
            />

            <div>
              <span className="block text-xs font-medium text-slate-500" id="accent-label">
                Accent Color
              </span>
              <div
                role="radiogroup"
                aria-labelledby="accent-label"
                className="mt-2 flex flex-wrap gap-3"
              >
                {ACCENT_OPTIONS.map((option) => {
                  const isActive = option === accent;
                  return (
                    <button
                      key={option}
                      type="button"
                      role="radio"
                      aria-checked={isActive}
                      aria-label={ACCENT_LABELS[option]}
                      title={ACCENT_LABELS[option]}
                      onClick={() => setAccent(option)}
                      className={`flex h-9 w-9 items-center justify-center rounded-full transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset ${
                        isActive ? "ring-2 ring-slate-900 ring-offset-2" : ""
                      }`}
                    >
                      <span
                        className={`h-7 w-7 rounded-full ${ACCENT_SWATCH_CLASSES[option]}`}
                        aria-hidden="true"
                      />
                    </button>
                  );
                })}
              </div>
            </div>
          </SettingsSection>

          <SettingsSection title="Workspace">
            <div>
              <SegmentedControl
                legend="Interface Density"
                options={DENSITY_OPTIONS}
                value={density}
                onChange={setDensity}
                renderOption={(option) => DENSITY_LABELS[option]}
              />
              <p className="mt-1.5 text-xs text-slate-400">{DENSITY_DESCRIPTIONS[density]}</p>
            </div>

            <SegmentedControl
              legend="Animations"
              options={ANIMATION_OPTIONS}
              value={animations}
              onChange={setAnimations}
              renderOption={(option) => (option === "enabled" ? "Enabled" : "Disabled")}
            />
          </SettingsSection>

          <SettingsSection title="About">
            <div className="space-y-1.5 text-sm text-slate-600">
              <p className="font-medium text-slate-900">
                Learn<span className="text-accent-600">Flow</span>{" "}
                <span className="font-normal text-slate-400">v0.1.0 &middot; V2.1</span>
              </p>
              <p>
                LearnFlow turns uploaded PDFs into study material and lets you chat with them,
                grounded in their actual content — summaries, flashcards, quizzes, mind maps, and
                retrieval-augmented chat across one or several documents at once.
              </p>
            </div>
          </SettingsSection>
        </div>
      </div>
    </div>
  );
}

export default SettingsPanel;
