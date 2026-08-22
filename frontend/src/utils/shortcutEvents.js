// Event names used to relay a few global keyboard shortcuts (Milestone
// 4) down to the specific component that owns the relevant action —
// e.g. Ctrl/Cmd+K is caught once at the top of the app (see AppShell)
// but the search input it should focus lives inside LibraryPanel,
// several components away. A plain DOM CustomEvent is a
// deliberately lightweight way to bridge that gap: no new context,
// no prop drilling through components that don't otherwise need to
// know about keyboard shortcuts at all, and a safe no-op if nothing
// is currently mounted to receive it (e.g. "new conversation" when no
// document is open).
export const FOCUS_SEARCH_EVENT = "learnflow:focus-search";
export const NEW_CONVERSATION_EVENT = "learnflow:new-conversation";

export function emitShortcutEvent(eventName) {
  window.dispatchEvent(new CustomEvent(eventName));
}
