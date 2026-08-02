import {
  ACCENT_OPTIONS,
  ANIMATION_OPTIONS,
  DENSITY_OPTIONS,
  THEME_OPTIONS,
  usePersonalization,
} from "../context/PersonalizationContext";
import Modal from "./Modal";

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
// setters. Dialog chrome (backdrop, focus trap, Escape, scroll lock)
// now comes from the shared Modal component (Milestone 4) rather than
// being implemented here directly.
function SettingsPanel({ onClose, onOpenShortcuts }) {
  const { theme, accent, density, animations, setTheme, setAccent, setDensity, setAnimations } =
    usePersonalization();

  function handleOpenShortcuts() {
    onClose();
    onOpenShortcuts?.();
  }

  return (
    <Modal title="Settings" onClose={onClose} maxWidthClassName="max-w-lg">
      <div className="space-y-8">
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
            {onOpenShortcuts && (
              <button
                type="button"
                onClick={handleOpenShortcuts}
                className="inline-flex items-center gap-1 rounded text-xs font-medium text-accent-700 hover:text-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                View keyboard shortcuts
                <span aria-hidden="true">&rarr;</span>
              </button>
            )}
          </div>
        </SettingsSection>
      </div>
    </Modal>
  );
}

export default SettingsPanel;
