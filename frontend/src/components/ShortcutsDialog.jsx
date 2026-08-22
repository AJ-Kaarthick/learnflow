import Modal from "./Modal";

// Mac uses ⌘, everything else uses Ctrl — detected once at module
// load rather than per-render since it can't change during a session.
const isMac =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
const MOD = isMac ? "⌘" : "Ctrl";

const SHORTCUTS = [
  { keys: [MOD, "K"], description: "Focus the document search" },
  { keys: [MOD, "Enter"], description: "Send the current chat message" },
  { keys: [MOD, "Shift", "N"], description: "Start a new conversation" },
  { keys: [MOD, "/"], description: "Open this shortcuts dialog" },
  { keys: ["Esc"], description: "Close Settings or any open dialog" },
];

function KeyCap({ children }) {
  return (
    <kbd className="inline-flex min-w-[1.5rem] items-center justify-center rounded border border-slate-300 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
      {children}
    </kbd>
  );
}

// Opens via Ctrl/Cmd+/ (see AppShell's global shortcut listener) or
// the "View keyboard shortcuts" link in Settings. Listing every
// shortcut is the whole job here — no search, per the brief, since
// five entries doesn't need one.
function ShortcutsDialog({ onClose }) {
  return (
    <Modal title="Keyboard Shortcuts" onClose={onClose} maxWidthClassName="max-w-sm">
      <ul className="space-y-3.5">
        {SHORTCUTS.map((shortcut) => (
          <li key={shortcut.description} className="flex items-center justify-between gap-4">
            <span className="text-sm text-slate-700">{shortcut.description}</span>
            <span className="flex shrink-0 items-center gap-1">
              {shortcut.keys.map((key, index) => (
                <span key={index} className="flex items-center gap-1">
                  {index > 0 && <span className="text-xs text-slate-300">+</span>}
                  <KeyCap>{key}</KeyCap>
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-5 border-t border-slate-100 pt-3 text-xs text-slate-400">
        Shortcuts are disabled while typing in a text field, except where the field itself is the
        target (e.g. sending a message).
      </p>
    </Modal>
  );
}

export default ShortcutsDialog;
