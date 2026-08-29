/**
 * Centralized localStorage-backed persistence for workspace session
 * state (V2.1 Milestone 2: "never lose your place" on refresh or when
 * switching documents). Every localStorage key LearnFlow writes lives
 * here — components call these helpers instead of touching
 * `window.localStorage` directly, so the storage schema stays in one
 * discoverable, versioned place instead of scattered across panels.
 *
 * localStorage can throw (private browsing in some browsers, storage
 * disabled, quota exceeded) and can hold stale/corrupt JSON left over
 * from an older version of the app. Every read and write below is
 * wrapped so a storage failure degrades to "nothing was restored",
 * never a crash — session persistence is a nice-to-have layered on
 * top of a working app, not something the app depends on to function.
 */

const NAMESPACE = "learnflow";
const SCHEMA_VERSION = 1;

const WORKSPACE_KEY = `${NAMESPACE}:workspace:v${SCHEMA_VERSION}`;
const SETTINGS_KEY = `${NAMESPACE}:settings:v${SCHEMA_VERSION}`;

// V2.4 Milestone 2 (frontend): `learnflow:conversations:v1` — the old
// per-document-combination full message history this module used to
// read and write (see the removed loadConversation/saveConversation/
// clearConversation/getConversationKey below in git history) — is
// deliberately NOT referenced anywhere in this file anymore. Chat
// conversations are now backend-persisted entities (see
// api/conversations.js), so the client only ever needs to remember
// *which* conversation was active (see activeConversationId below),
// never its messages. Any pre-Milestone-2 data still sitting under
// that old key in a returning user's browser is simply left alone —
// unread, unwritten, and harmless — rather than actively cleared,
// per this milestone's "don't silently discard existing localStorage
// data" requirement.

// Only meaningful, restorable state lives here — no loading flags,
// in-flight requests, or transient UI (typing indicators, temporary
// errors), per the V2.1 Milestone 2 brief.
const DEFAULT_WORKSPACE_STATE = {
  activeDocumentId: null,
  activeStudyTab: "summary",
  // V2.4 Milestone 2 (frontend): replaces the old `selectedDocumentIds`
  // field. Chat's document selection is now a property of the active
  // *conversation* (persisted server-side as ConversationDocument
  // rows — see api/conversations.js), not free-floating client state,
  // so the only thing Chat still needs restored across a refresh is
  // which conversation was active — see loadActiveConversationId/
  // saveActiveConversationId below. A workspace blob saved before this
  // milestone may still have a `selectedDocumentIds` array in it; the
  // merge in loadWorkspaceState just leaves it as an ignored, unread
  // extra property rather than an error.
  activeConversationId: null,
  librarySearch: "",
  librarySort: "uploaded_newest",
  libraryScrollTop: 0,
};

function readRaw(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Storage can be unavailable entirely — treat exactly like
    // "nothing has been saved yet".
    return null;
  }
}

function writeRaw(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Best-effort only. A failed save should never break the
    // workspace itself — worst case the user just doesn't get that
    // piece of state back after a refresh.
  }
}

function safeParseObject(raw, fallback) {
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------
// Workspace state: active document, active study tab, the active
// conversation's id, and the library's search/sort/scroll.
// ---------------------------------------------------------------------

function loadWorkspaceState() {
  const stored = safeParseObject(readRaw(WORKSPACE_KEY), {});
  return { ...DEFAULT_WORKSPACE_STATE, ...stored };
}

function patchWorkspaceState(patch) {
  const next = { ...loadWorkspaceState(), ...patch };
  writeRaw(WORKSPACE_KEY, JSON.stringify(next));
}

export function loadActiveDocumentId() {
  return loadWorkspaceState().activeDocumentId;
}

export function saveActiveDocumentId(documentId) {
  patchWorkspaceState({ activeDocumentId: documentId ?? null });
}

export function loadActiveStudyTab() {
  return loadWorkspaceState().activeStudyTab;
}

export function saveActiveStudyTab(tab) {
  patchWorkspaceState({ activeStudyTab: tab });
}

// The identity of the active conversation only — never its messages
// or documents, both of which the backend already persists in full
// (see api/conversations.js's getConversation). This is what fulfills
// requirement 3 of V2.4 Milestone 2 (frontend): "the client should
// only persist the identity of the active conversation ... not
// duplicate full conversation state in localStorage." Restoring after
// a refresh is then just: read this id, GET /conversations/{id}, and
// if that 404s (the conversation was deleted elsewhere) fall back to
// picking a different one — see ChatPage.jsx.
export function loadActiveConversationId() {
  return loadWorkspaceState().activeConversationId;
}

export function saveActiveConversationId(conversationId) {
  patchWorkspaceState({ activeConversationId: conversationId ?? null });
}

export function loadLibraryFilters() {
  const state = loadWorkspaceState();
  return { search: state.librarySearch, sort: state.librarySort };
}

export function saveLibraryFilters({ search, sort }) {
  patchWorkspaceState({ librarySearch: search, librarySort: sort });
}

export function loadLibraryScrollTop() {
  return loadWorkspaceState().libraryScrollTop;
}

export function saveLibraryScrollTop(scrollTop) {
  patchWorkspaceState({ libraryScrollTop: scrollTop });
}

// ---------------------------------------------------------------------
// Personalization settings: theme, accent color, workspace density,
// and animation preference (V2.1 Milestone 3). Kept in their own key,
// separate from workspace/conversation state, because they're
// conceptually different (persistent preferences vs. session/content
// state) and are read synchronously and very early — before first
// paint, from index.html's inline script (see the "flash of wrong
// theme" note there) — so isolating them keeps that early read cheap
// and avoids ever parsing conversation history just to know the
// theme. Same localStorage-via-this-module discipline as the rest of
// the file: no component reads or writes `learnflow:settings:*`
// directly.
const DEFAULT_SETTINGS = {
  theme: "system", // "light" | "dark" | "system"
  accent: "blue", // "blue" | "purple" | "green" | "orange"
  density: "comfortable", // "comfortable" | "compact"
  // Defaults to the OS-level reduced-motion preference on first run
  // (nothing saved yet) so a user who has already told their system
  // to minimize motion gets that respected immediately, without
  // having to find this app's own setting first. Once something is
  // saved, that explicit choice always wins over the OS preference.
  animations:
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "disabled"
      : "enabled",
};

export function loadSettings() {
  const stored = safeParseObject(readRaw(SETTINGS_KEY), {});
  return { ...DEFAULT_SETTINGS, ...stored };
}

export function saveSettings(settings) {
  writeRaw(SETTINGS_KEY, JSON.stringify(settings));
}
