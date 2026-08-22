import { useEffect, useState } from "react";
import ShortcutsDialog from "./ShortcutsDialog";
import TopBar from "./TopBar";
import { FOCUS_SEARCH_EVENT, NEW_CONVERSATION_EVENT, emitShortcutEvent } from "../utils/shortcutEvents";

// Form fields where a bare letter/slash keystroke is normal typing,
// not a shortcut attempt — the global listener below ignores its
// shortcuts entirely while one of these is focused. Ctrl/Cmd+Enter is
// the one exception, and it isn't handled here at all — it's a local
// keydown handler on the chat composer itself (see ChatPanel), since
// that input *is* the intended target for it.
const TEXT_ENTRY_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

// V2.4 Milestone 1: the three-panel workspace (Library | Study | AI
// Assistant) that used to be the entire app is now one possible page
// (see StudyPage) alongside Home and the new dedicated ChatPage — so
// the layout that locks the shell to the viewport and manages
// independent per-column scrolling has moved down into each page,
// which knows its own column structure. What's left here is exactly
// what's still true regardless of which page is showing: the brand/
// nav/settings header, the global keyboard shortcuts that aren't
// scoped to one particular input, and the outer viewport lock so no
// page accidentally scrolls the whole browser window instead of its
// own content.
function AppShell({ route, children }) {
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    function handleKeyDown(event) {
      const isModifierHeld = event.metaKey || event.ctrlKey;
      if (!isModifierHeld) return;
      if (TEXT_ENTRY_TAGS.has(event.target?.tagName)) return;

      const key = event.key.toLowerCase();

      if (key === "k" && !event.shiftKey) {
        event.preventDefault();
        emitShortcutEvent(FOCUS_SEARCH_EVENT);
      } else if (key === "/" && !event.shiftKey) {
        event.preventDefault();
        setShortcutsOpen(true);
      } else if (key === "n" && event.shiftKey) {
        // Note: Chrome reserves Ctrl/Cmd+Shift+N for "New Incognito
        // Window" at the browser-chrome level — preventDefault() here
        // can't override that, so this combo simply won't reach the
        // page in Chrome. It works as documented in Firefox and
        // Safari.
        event.preventDefault();
        emitShortcutEvent(NEW_CONVERSATION_EVENT);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col bg-surface lg:h-screen lg:overflow-hidden">
      {/* Visually hidden until focused. Uses a click handler rather
          than a real `href="#main-content"` fragment link because the
          URL hash is now the app's router (see useHashRoute) —
          navigating it here would be read as "go to this route"
          instead of "scroll/focus this element". */}
      <a
        href="#"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("page-content")?.focus();
        }}
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to main content
      </a>

      <TopBar route={route} onOpenShortcuts={() => setShortcutsOpen(true)} />

      <div id="page-content" tabIndex={-1} className="flex flex-1 flex-col lg:min-h-0">
        {children}
      </div>

      {shortcutsOpen && <ShortcutsDialog onClose={() => setShortcutsOpen(false)} />}
    </div>
  );
}

export default AppShell;
