import { useEffect, useRef } from "react";

// Shared accessible dialog chrome (Milestone 4): backdrop, Escape-to-
// close, Tab focus trap, background scroll lock, and the header/close
// button row. Extracted from Settings (Milestone 3, which previously
// implemented all of this itself) so the new Keyboard Shortcuts
// dialog doesn't duplicate the same focus-management logic — any
// future modal in the app should build on this rather than
// reimplementing it.
function Modal({ title, onClose, children, maxWidthClassName = "max-w-lg" }) {
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  // Focus the dialog on open, close on Escape, and trap Tab within it
  // — a modal dialog shouldn't let keyboard focus leak out to the
  // workspace behind it while it's open.
  useEffect(() => {
    closeButtonRef.current?.focus();

    function handleKeyDown(event) {
      // Swallow every keydown while this modal is open, after handling
      // the ones it cares about — otherwise a key it doesn't act on
      // (e.g. Ctrl/Cmd+/) would keep bubbling up to AppShell's
      // window-level shortcut listener and could, for instance, open
      // the Shortcuts dialog stacked on top of this one. A focused
      // modal should own keyboard handling until it's closed.
      event.stopPropagation();

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
    // Prevents the page behind the dialog from scrolling while it's
    // open, same reasoning as AppShell/each page locking to one
    // scroll container at a time.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  const titleId = `modal-title-${title.replace(/\s+/g, "-").toLowerCase()}`;

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
        aria-labelledby={titleId}
        className={`flex max-h-[85vh] w-full ${maxWidthClassName} flex-col overflow-hidden rounded-xl bg-surface shadow-xl`}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold tracking-tight text-slate-900">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label={`Close ${title.toLowerCase()}`}
            className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

export default Modal;
