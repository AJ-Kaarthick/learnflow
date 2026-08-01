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
const CONVERSATIONS_KEY = `${NAMESPACE}:conversations:v${SCHEMA_VERSION}`;
const SETTINGS_KEY = `${NAMESPACE}:settings:v${SCHEMA_VERSION}`;

// Only meaningful, restorable state lives here — no loading flags,
// in-flight requests, or transient UI (typing indicators, temporary
// errors), per the V2.1 Milestone 2 brief.
const DEFAULT_WORKSPACE_STATE = {
  activeDocumentId: null,
  activeStudyTab: "summary",
  selectedDocumentIds: [],
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
// Workspace state: active document, active study tab, selected
// documents, and the library's search/sort/scroll — everything except
// conversations, which get their own key below (see "Conversations").
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

export function loadSelectedDocumentIds() {
  return loadWorkspaceState().selectedDocumentIds;
}

export function saveSelectedDocumentIds(documentIds) {
  patchWorkspaceState({ selectedDocumentIds: documentIds });
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
// Conversations: one chat history per unique document combination.
//
// Keyed by *document ids*, never filenames — a rename (see
// DocumentList) must not orphan a conversation. Multi-document
// conversations use *sorted* ids so selecting [Linux, OS] and
// [OS, Linux] read and write the exact same conversation, matching
// how AssistantPanel already keys/remounts ChatPanel.
// ---------------------------------------------------------------------

export function getConversationKey(documentIds) {
  return documentIds.slice().sort().join(",");
}

function loadConversationsMap() {
  return safeParseObject(readRaw(CONVERSATIONS_KEY), {});
}

export function loadConversation(conversationKey) {
  return loadConversationsMap()[conversationKey] ?? [];
}

export function saveConversation(conversationKey, messages) {
  const all = loadConversationsMap();
  all[conversationKey] = messages;
  writeRaw(CONVERSATIONS_KEY, JSON.stringify(all));
}

export function clearConversation(conversationKey) {
  const all = loadConversationsMap();
  delete all[conversationKey];
  writeRaw(CONVERSATIONS_KEY, JSON.stringify(all));
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
