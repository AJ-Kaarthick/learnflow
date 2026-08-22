import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { indexDocument, sendChatMessage, sendMultiDocumentChatMessage } from "../api/chat";
import { clearConversation, getConversationKey, loadConversation, saveConversation } from "../utils/persistence";
import { NEW_CONVERSATION_EVENT } from "../utils/shortcutEvents";
import { describeUnreadableDocuments, splitDocumentsByReadability } from "../utils/documentReadiness";
import ExpandableText from "./ExpandableText";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

// Small icon-only buttons under an assistant message (Copy/Regenerate)
// share this — smaller and quieter than SECONDARY_BUTTON_CLASSES,
// which is sized for a labeled action, not an icon sitting quietly
// under a bubble until it's needed.
const MESSAGE_ACTION_BUTTON_CLASSES =
  "inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

// How close to the bottom (in pixels) still counts as "at the
// bottom" for auto-scroll purposes — a few pixels of rounding/
// sub-pixel scroll slack shouldn't count as the user having
// deliberately scrolled up.
const BOTTOM_THRESHOLD_PX = 56;

// How long the "Copied!" confirmation stays up before reverting.
const COPY_FEEDBACK_MS = 1500;

// V2.4 Milestone 1: the composer's tallest allowed height (in pixels)
// before it stops growing and scrolls internally instead — roughly
// 8-9 lines of text-sm/leading-relaxed copy, generous enough for a
// long pasted question while still leaving the message list above it
// with real room on a full Chat page.
const COMPOSER_MAX_HEIGHT_PX = 200;

function formatTimestamp(epochMs) {
  if (!epochMs) return null;
  try {
    return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(
      new Date(epochMs)
    );
  } catch {
    return null;
  }
}

// Assistant answers render as real markdown now (Milestone 4) instead
// of the old hand-rolled bold+bullet-list-only formatter — react-
// markdown + remark-gfm (tables, strikethrough) covers everything the
// brief asks for (headings, emphasis, code, ordered/nested lists,
// blockquotes, hr, tables) without a bespoke parser to maintain.
// Styled via @tailwindcss/typography's `prose`, re-themed to
// LearnFlow's own tokens in the `.chat-markdown` rules in index.css
// rather than typography's default palette. User messages deliberately
// stay plain text below (see ChatMessageBubble) — a raw question is
// rarely markdown, and rendering it as such would be more likely to
// mangle a stray "*" or "_" than to help.
function ChatMarkdown({ content }) {
  return (
    <div className="chat-markdown prose prose-sm max-w-none break-words prose-p:my-2 prose-headings:my-2 first:prose-p:mt-0 last:prose-p:mb-0 first:prose-headings:mt-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          table: (props) => (
            <div className="overflow-x-auto">
              <table {...props} />
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Match-score badge for a retrieved source chunk (Milestone 4: "better
// source presentation"). Purely a presentation tier over the same
// `source.score` the backend already returns — no backend change, no
// change to what score means, just three visual bands so a skim of
// the source list shows at a glance which excerpts the retrieval was
// most confident in.
function MatchScoreBadge({ score }) {
  const percent = Math.round(score * 100);
  const tierClasses =
    percent >= 80
      ? "bg-accent-50 text-accent-700"
      : percent >= 60
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-100 text-slate-500";

  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide ${tierClasses}`}>
      {percent}% match
    </span>
  );
}

// Renders one turn of the conversation. Kept inside this file rather
// than a separate component file, same as every other panel's small
// per-item renderers (e.g. flashcard cards in FlashcardsPanel) —
// reusable within the panel without needing its own file.
function ChatMessageBubble({ message, isLast, isSending, copiedMessageId, onCopy, onRegenerate }) {
  const isUser = message.role === "user";
  const isCopied = copiedMessageId === message.id;
  const timestamp = formatTimestamp(message.createdAt);
  const canRegenerate = isLast && !isUser && !message.isError && !isSending;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[92%] space-y-1 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-accent-600 px-4 py-2.5 text-sm leading-relaxed text-white"
              : message.isError
                ? "rounded-2xl rounded-tl-sm border border-red-200 bg-red-50 px-4 py-2.5 text-sm leading-relaxed text-red-700"
                : "space-y-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-surface px-4 py-2.5 text-sm leading-relaxed text-slate-800"
          }
        >
          {isUser || message.isError ? (
            // V2.4 Milestone 1 UX polish (issue 4): plain-text messages
            // (never markdown — see ChatMarkdown's note above) get a
            // generous max-height with internal scrolling once
            // exceeded, same "cap + scroll" pattern as the composer
            // itself (see COMPOSER_MAX_HEIGHT_PX), so one very long
            // pasted message can't blow up the bubble to fill the
            // entire message list — the rest of the conversation stays
            // reachable above/below it. 320px is deliberately generous
            // (well over a dozen lines at this text size) so short and
            // medium messages, including a normal multi-sentence
            // question, never come close to it. break-words stops a
            // long unbroken token (a URL, a hash) from overflowing the
            // bubble horizontally instead of wrapping.
            <p className="max-h-80 overflow-y-auto whitespace-pre-wrap break-words">
              {message.content}
            </p>
          ) : (
            <ChatMarkdown content={message.content} />
          )}
        </div>

        {/* Timestamp + actions row. Timestamp is optional per the
            brief ("if they integrate naturally") — it only renders for
            messages that have one, so conversations restored from
            before this milestone (no `createdAt` in storage) just
            show the actions without a blank gap. */}
        <div className={`flex items-center gap-2 px-1 ${isUser ? "justify-end" : "justify-start"}`}>
          {timestamp && <span className="text-[11px] text-slate-400">{timestamp}</span>}
          {!isUser && !message.isError && (
            <>
              <button
                type="button"
                onClick={() => onCopy(message)}
                className={MESSAGE_ACTION_BUTTON_CLASSES}
              >
                {isCopied ? "Copied!" : "Copy"}
              </button>
              {canRegenerate && (
                <button type="button" onClick={onRegenerate} className={MESSAGE_ACTION_BUTTON_CLASSES}>
                  Regenerate
                </button>
              )}
            </>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <details className="group overflow-hidden rounded-xl border border-slate-200 bg-surface text-xs text-slate-600">
            <summary className="flex cursor-pointer select-none list-none items-center justify-between gap-2 px-3.5 py-2.5 font-medium text-slate-500 marker:content-none transition-colors hover:bg-slate-50 hover:text-slate-700">
              <span className="inline-flex items-center gap-1.5">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 text-slate-400" aria-hidden="true">
                  <path
                    fillRule="evenodd"
                    d="M4 4a2 2 0 0 1 2-2h5.172a2 2 0 0 1 1.414.586l2.828 2.828A2 2 0 0 1 16 6.828V16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Zm7 1a1 1 0 1 0-2 0v3.586L7.707 7.293a1 1 0 0 0-1.414 1.414l3 3a1 1 0 0 0 1.414 0l3-3a1 1 0 0 0-1.414-1.414L11 8.586V5Z"
                    clipRule="evenodd"
                  />
                </svg>
                {message.sources.length} {message.sources.length === 1 ? "source" : "sources"}
              </span>
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-3.5 w-3.5 shrink-0 transition-transform group-open:rotate-180"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.24 4.5a.75.75 0 0 1-1.08 0l-4.24-4.5a.75.75 0 0 1 .02-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            </summary>
            <ul className="space-y-2 border-t border-slate-100 p-2.5">
              {message.sources.map((source, index) => (
                <li key={source.chunk_id} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-1.5">
                      <span className="shrink-0 rounded-full bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-slate-400">
                        {index + 1}
                      </span>
                      {/* Only present for multi-document chat (see
                          MultiDocumentSourceItem in schemas/chat.py) —
                          single-document sources omit it since there's
                          only one document to begin with. */}
                      {source.document_name && (
                        <p className="truncate font-medium text-slate-600">{source.document_name}</p>
                      )}
                    </div>
                    <MatchScoreBadge score={source.score} />
                  </div>
                  <ExpandableText text={source.content} textClassName="text-slate-600" fadeFromClassName="from-slate-50" />
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

function ChatPanel({ documents }) {
  // V2.4 Milestone 1 UX polish (issue 2): split the selection into
  // documents Chat can actually use vs. ones with no readable text
  // (splitDocumentsByReadability — same per-document signal Study
  // generation already gates on, see documentReadiness.js). Only the
  // readable group is ever indexed or sent to the chat endpoints
  // below, so one unreadable document in a multi-document selection
  // can never block the others (issue 3) — and unreadableDocuments is
  // what lets this panel name exactly which file(s) it left out
  // (issue 4), instead of the old backend copy that only ever said
  // "this document" (or, for the single-document route, a raw
  // document id).
  const { readable: readableDocuments, unreadable: unreadableDocuments } =
    splitDocumentsByReadability(documents);
  const documentIds = readableDocuments.map((document) => document.id);
  const isMultiDocument = documentIds.length > 1;
  const hasUsableDocuments = documentIds.length > 0;

  // One conversation per unique set of *usable* documents, keyed by
  // sorted document ids (never filenames — see getConversationKey).
  // Deliberately keyed off readableDocuments, not the raw `documents`
  // prop: a document with no readable text never contributes
  // anything to retrieval or the answer (see chat_service.py), so a
  // selection of [Linux-Tutorial.pdf, Enso-Wallpaper.jpg] is, as far
  // as the actual conversation is concerned, the same conversation as
  // [Linux-Tutorial.pdf] alone — and should read/write the same
  // history, including if the user later deselects the unreadable
  // file. Stable across this component's whole lifetime either way:
  // AssistantPanel remounts ChatPanel (via its `key`, based on the
  // full raw selection) whenever the selection actually changes, so
  // `documents` — and therefore this key — never changes out from
  // under an already-mounted instance.
  //
  // Falls back to the full raw selection's ids when there are no
  // usable documents at all (documentIds would otherwise collapse to
  // the same empty key "" for every such selection) — this state
  // never actually shows a conversation (see indexStatus === "error"
  // below, which hides the whole message list/composer), so this
  // only prevents unrelated all-unreadable selections from sharing
  // one meaningless storage slot.
  const conversationKey = getConversationKey(
    hasUsableDocuments ? documentIds : documents.map((document) => document.id)
  );

  const [indexStatus, setIndexStatus] = useState("indexing"); // indexing | ready | error
  const [indexError, setIndexError] = useState("");

  // Restored lazily from storage on mount rather than always starting
  // at [] — this is what makes returning to a document (or document
  // combination) bring its previous conversation back automatically.
  const [messages, setMessages] = useState(() => loadConversation(conversationKey));
  const [question, setQuestion] = useState("");
  const [sendStatus, setSendStatus] = useState("idle"); // idle | sending
  const [copiedMessageId, setCopiedMessageId] = useState(null);

  // V2.4 Milestone 1 UX polish: whether *this mount* restored a
  // non-empty conversation, snapshotted once at mount rather than
  // recomputed from `messages` on every render — recomputing would
  // make the "Existing conversation" badge below reflect "there are
  // currently messages" (trivially true the instant the user sends
  // their first message in a brand-new conversation, since it's
  // already visible right there in the message list) instead of what
  // it's actually meant to answer: "did I already talk to this exact
  // combination before now?" A ref (not state) because it never
  // changes the panel's own render output on its own — it's read
  // during render, but nothing should re-render because of it.
  const hadExistingConversationRef = useRef(messages.length > 0);

  // The in-flight request's AbortController (Milestone 4: "Stop
  // generation"). This endpoint isn't streamed — there's no partial
  // answer to interrupt mid-token — so "stop" means "stop waiting on
  // and discard whatever comes back", not "cut off the model
  // mid-sentence". That's still a meaningful, honest version of the
  // feature for a non-streaming architecture: it immediately frees the
  // input for a new question instead of forcing a wait.
  const abortControllerRef = useRef(null);
  const copiedTimeoutRef = useRef(null);

  // The composer textarea — its height is measured and set directly
  // (see the auto-grow effect below) rather than left to CSS alone,
  // since "grow up to a max height, then scroll" needs the element's
  // own scrollHeight to know when content has actually exceeded that
  // cap.
  const textareaRef = useRef(null);

  // The scrollable message list itself — scrolling is applied
  // directly to this element (el.scrollTo), never via
  // Element.scrollIntoView(), which walks up and can also scroll
  // ancestor containers (including, previously, the whole browser
  // page) into view. Scrolling only this element is what guarantees
  // sending a message can never move anything outside this panel.
  const messagesContainerRef = useRef(null);

  // Whether the user is (near) the bottom of the conversation right
  // now — a ref, not state, because it needs to reflect the truth at
  // the instant a new message arrives without waiting for a render.
  // ChatGPT/Gemini-style rule: only auto-scroll for new content if the
  // user was already at the bottom; otherwise leave their scroll
  // position alone and surface "Scroll to latest" instead.
  const isAtBottomRef = useRef(true);
  const [showScrollToLatest, setShowScrollToLatest] = useState(false);

  // Tracks whether the scroll-to-latest-message effect below is
  // running for this panel's first render. AssistantPanel remounts
  // ChatPanel (via its `key`) every time the document selection
  // changes — opening a document from the library, or checking/
  // unchecking one — which made the effect fire on that very first
  // render too and jump straight to an empty, just-mounted chat panel
  // the user hadn't asked to see. Skipping the first run keeps the
  // intended behavior (scroll to the newest message as the
  // conversation grows) without moving anything on mount.
  const isFirstRender = useRef(true);

  function scrollMessagesToBottom(behavior = "smooth") {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior });
  }

  function handleMessagesScroll() {
    const container = messagesContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const atBottom = distanceFromBottom < BOTTOM_THRESHOLD_PX;
    isAtBottomRef.current = atBottom;
    if (atBottom) setShowScrollToLatest(false);
  }

  async function prepareChat() {
    if (!hasUsableDocuments) {
      // Every selected document has no readable text — there is
      // nothing to index or chat with, so skip the network round trip
      // entirely rather than calling the index endpoint just to get
      // back its own version of this same fact (see
      // splitDocumentsByReadability above, and requirement 8: reuse
      // the readiness signal the app already has instead of a new
      // detection path). describeUnreadableDocuments produces the
      // same "which file(s), why" wording used below for the partial
      // case, with readableCount 0 so it skips the "others still
      // work" reassurance, which wouldn't be true here.
      setIndexStatus("error");
      setIndexError(describeUnreadableDocuments(unreadableDocuments, 0));
      return;
    }

    setIndexStatus("indexing");
    setIndexError("");
    try {
      // Every selected *readable* document needs to be indexed before
      // it can be searched — each call is independent (a document
      // indexed for one conversation stays indexed), so these run in
      // parallel rather than one at a time. Documents with no
      // readable text are deliberately excluded from `documentIds`
      // (see above) — indexing them would just reproduce, via a 422
      // round trip, a fact this panel already knows client-side, and
      // would incorrectly fail the whole Promise.all for documents
      // that have nothing wrong with them (issue 3).
      await Promise.all(documentIds.map((documentId) => indexDocument(documentId)));
      setIndexStatus("ready");
    } catch (error) {
      setIndexStatus("error");
      setIndexError(error.message);
    }
  }

  // Runs once when this panel mounts. AssistantPanel keys ChatPanel by
  // the current document selection, so selecting a different set of
  // documents (or uploading a new one) remounts a fresh instance —
  // that's also what starts a *different* conversation (see
  // conversationKey / loadConversation above), with no extra reset
  // logic needed here.
  useEffect(() => {
    prepareChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentIds.join(",")]);

  // Keeps this conversation's saved copy in sync as it grows (or is
  // cleared — see handleNewConversation) so switching away and back,
  // or refreshing the page, picks it back up from here.
  useEffect(() => {
    saveConversation(conversationKey, messages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationKey, messages]);

  // If this mount restored a non-empty conversation (see the
  // `messages` initializer above), jump straight to its most recent
  // message instead of showing the top of a long history — instant,
  // not smooth, since this is establishing the initial view rather
  // than reacting to a new message arriving.
  useEffect(() => {
    scrollMessagesToBottom("auto");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (isAtBottomRef.current) {
      scrollMessagesToBottom();
    } else {
      // The user scrolled up to read something earlier — respect
      // that. Don't move their view; just let them know there's new
      // content waiting below.
      setShowScrollToLatest(true);
    }
  }, [messages, sendStatus]);

  // Cleans up the abort controller and the "Copied!" timeout if the
  // panel unmounts mid-request/mid-feedback — e.g. the user switches
  // documents while a question is still in flight.
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (copiedTimeoutRef.current) clearTimeout(copiedTimeoutRef.current);
    };
  }, []);

  // Shared by both a normal send and a regenerate — the only
  // difference between them is what `question`/`history` they pass in
  // and what they've already done to `messages` before calling this
  // (see handleSubmit and handleRegenerate below), so the actual
  // network call, abort wiring, and success/error handling live here
  // once rather than twice.
  async function askQuestion(trimmedQuestion, history) {
    setSendStatus("sending");
    isAtBottomRef.current = true;
    setShowScrollToLatest(false);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Single document keeps using the original, unchanged endpoint
      // (POST /documents/{id}/chat) — same call as before multi-
      // document chat existed. Multiple documents use the new
      // POST /documents/chat, which also returns which document each
      // source came from (see ChatMessageBubble).
      const result = isMultiDocument
        ? await sendMultiDocumentChatMessage(documentIds, trimmedQuestion, {
            history,
            signal: controller.signal,
          })
        : await sendChatMessage(documentIds[0], trimmedQuestion, {
            history,
            signal: controller.signal,
          });

      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: result.answer,
          sources: result.sources,
          createdAt: Date.now(),
        },
      ]);
    } catch (error) {
      if (error.name === "AbortError") {
        // User pressed Stop — an intentional cancellation, not a
        // failure, so no error bubble.
        return;
      }
      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content: error.message,
          isError: true,
          createdAt: Date.now(),
        },
      ]);
    } finally {
      abortControllerRef.current = null;
      setSendStatus("idle");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    submitCurrentQuestion();
  }

  // Split out from handleSubmit so the Ctrl/Cmd+Enter handler on the
  // input (below) can trigger the exact same send without needing a
  // fake form-submit event.
  function submitCurrentQuestion() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || sendStatus === "sending" || indexStatus !== "ready") return;

    // Turns already in this conversation, sent along so the backend
    // can resolve follow-ups like "explain that more simply" without
    // the user repeating the original topic. Error bubbles aren't
    // real assistant content, so they're excluded. How much of this
    // actually gets used is the backend's call (see MAX_HISTORY_TURNS
    // in chat_service.py) — this just relays what's currently here.
    const history = messages
      .filter((message) => !message.isError)
      .map((message) => ({ role: message.role, content: message.content }));

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content: trimmedQuestion,
      createdAt: Date.now(),
    };
    setMessages((previous) => [...previous, userMessage]);
    setQuestion("");
    askQuestion(trimmedQuestion, history);
  }

  // Regenerate (Milestone 4): re-asks the same last question, in place
  // of the last assistant answer. Only ever enabled for the most
  // recent turn (see ChatMessageBubble's `canRegenerate`), same as
  // ChatGPT/Claude — regenerating an answer from the middle of a
  // conversation would leave the turns after it referring to an
  // answer that no longer exists.
  function handleRegenerate() {
    if (sendStatus === "sending" || messages.length < 2) return;
    const lastMessage = messages[messages.length - 1];
    const lastUserMessage = messages[messages.length - 2];
    if (lastMessage.role !== "assistant" || lastMessage.isError) return;
    if (lastUserMessage.role !== "user") return;

    const history = messages
      .slice(0, messages.length - 2)
      .filter((message) => !message.isError)
      .map((message) => ({ role: message.role, content: message.content }));

    // Drop the answer being replaced first, so the "Thinking..."
    // indicator appears in its place while the new one is generated.
    setMessages((previous) => previous.slice(0, previous.length - 1));
    askQuestion(lastUserMessage.content, history);
  }

  function handleStop() {
    abortControllerRef.current?.abort();
  }

  function handleCopyMessage(message) {
    if (!navigator.clipboard) return;
    navigator.clipboard
      .writeText(message.content)
      .then(() => {
        if (copiedTimeoutRef.current) clearTimeout(copiedTimeoutRef.current);
        setCopiedMessageId(message.id);
        copiedTimeoutRef.current = setTimeout(() => setCopiedMessageId(null), COPY_FEEDBACK_MS);
      })
      .catch(() => {
        // Clipboard access denied/unavailable — nothing useful to do
        // beyond leaving the button in its normal state.
      });
  }

  // Starts a fresh conversation for the *current* chat context only.
  // Deliberately narrow: it clears `messages` and this conversation's
  // entry in storage, and nothing else — not other conversations
  // (they're stored under their own keys), not this document's
  // summary/flashcards/quiz/mind map (entirely separate state, owned
  // by StudyWorkspace's panels, never touched here). Guarded
  // internally (not just via the button's `disabled`) so the Ctrl/Cmd+
  // Shift+N shortcut below can call it unconditionally and safely.
  function handleNewConversation() {
    if (messages.length === 0 || sendStatus === "sending") return;
    setMessages([]);
    clearConversation(conversationKey);
    setQuestion("");
    isAtBottomRef.current = true;
    setShowScrollToLatest(false);
    // The conversation this badge described no longer exists — clear
    // it too, or starting fresh would still be labeled "Existing
    // conversation" for the rest of this mount.
    hadExistingConversationRef.current = false;
  }

  // Ctrl/Cmd+Shift+N (Milestone 4) is caught globally in AppShell (it
  // isn't scoped to any particular input) and relayed here via a
  // CustomEvent — see utils/shortcutEvents.js for why. Only the
  // currently-mounted ChatPanel, if any, is listening, so this is a
  // safe no-op whenever the assistant panel has no document open.
  useEffect(() => {
    window.addEventListener(NEW_CONVERSATION_EVENT, handleNewConversation);
    return () => window.removeEventListener(NEW_CONVERSATION_EVENT, handleNewConversation);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, sendStatus, conversationKey]);

  // V2.4 Milestone 1 UX polish: the composer grows with the prompt (up
  // to COMPOSER_MAX_HEIGHT_PX, then scrolls internally instead — see
  // the textarea's `style` below) rather than staying a fixed single
  // line. Resetting to "auto" before reading scrollHeight is what
  // lets the box shrink back down again too (e.g. after clearing a
  // long question on send) — without it, scrollHeight would only
  // ever reflect the tallest the box has already been.
  //
  // Issue 4 follow-up (manual-testing feedback): the growth itself
  // worked, but with no `transition` on the textarea, each line the
  // box grew by was an instant snap rather than a smooth resize —
  // felt abrupt, especially on the first jump from one line to two.
  // The `transition-[height]` class on the textarea below is what's
  // actually responsible for the smoothing; this effect still just
  // computes the target pixel height every keystroke, exactly as
  // before — the browser animates the change on its own once a
  // transition is declared, no extra JS needed.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, COMPOSER_MAX_HEIGHT_PX)}px`;
  }, [question]);

  function handleQuestionKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      submitCurrentQuestion();
      return;
    }
    // Plain Enter submits, same as the old single-line input's native
    // form-submit-on-Enter behavior; Shift+Enter inserts a newline
    // instead, for the (now-possible, since this is a real textarea)
    // case of a prompt the user wants to format across lines before
    // sending.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitCurrentQuestion();
    }
  }

  const isSending = sendStatus === "sending";
  const inputDisabled = indexStatus !== "ready" || isSending;
  const documentsLabel = isMultiDocument ? "documents" : "document";

  // V2.4 Milestone 1 UX polish (issue 2): distinguishes "every
  // selected document has no readable text" (a permanent fact — see
  // prepareChat's early return above, which sets indexError to
  // describeUnreadableDocuments(unreadableDocuments, 0) without ever
  // calling the backend — retrying can't fix it, so there's no point
  // offering a retry) from every other indexing failure (network
  // blip, AI provider down, etc. on one of the *readable* documents),
  // which stays exactly as it was — still worth a retry, still framed
  // as a chat-prep failure. Driven by hasUsableDocuments (the same
  // readability split used everywhere else in this panel) rather than
  // matching indexError's text, so it stays correct regardless of
  // exactly how that message is worded.
  const isBlockedByUnreadableText = indexStatus === "error" && !hasUsableDocuments;

  // Partial case (issue 2/3/4): at least one selected document has no
  // readable text, but at least one other is fine, so Chat proceeds
  // using only the readable ones (see documentIds above). This is
  // what tells the user which file(s) got left out and why — shown
  // regardless of indexStatus (indexing or ready) since it's a fact
  // about the *selection*, not a transient prep failure, and needs to
  // stay visible for as long as those documents remain selected.
  const unreadableDocumentsNotice =
    unreadableDocuments.length > 0 && hasUsableDocuments
      ? describeUnreadableDocuments(unreadableDocuments, documentIds.length)
      : null;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold tracking-tight text-slate-900">Chat</h3>
          {/* V2.4 Milestone 1 UX polish (issue 1): the only signal
              this document combination had prior history used to be
              noticing the restored bubbles further down — easy to
              miss, and no signal at all until indexing finished. This
              badge answers "have I chatted with this combination
              before" immediately, without introducing any new
              persistence — see hadExistingConversationRef above. */}
          {hadExistingConversationRef.current && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-0.5 text-[11px] font-medium text-accent-700"
              title="You've chatted with this document combination before — your previous messages are shown below."
            >
              <span className="h-1.5 w-1.5 rounded-full bg-accent-500" aria-hidden="true" />
              Existing conversation
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {indexStatus === "indexing" && (
            <span className="flex items-center gap-2 text-xs text-slate-500">
              <span
                className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-accent-600"
                aria-hidden="true"
              />
              Preparing {documentsLabel}...
            </span>
          )}
          <button
            type="button"
            onClick={handleNewConversation}
            disabled={messages.length === 0 || isSending}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40"
          >
            New conversation
          </button>
        </div>
      </div>

      {/* Which documents this conversation is grounded in is shown by
          the caller (see AssistantPanel's chip row above this panel,
          which also lets the user remove one) — not repeated here, so
          the same information isn't shown twice back-to-back. */}

      {/* V2.4 Milestone 1 UX polish (issue 2): identifies the
          unreadable document(s) by filename while the rest of the
          selection stays fully usable below — see
          unreadableDocumentsNotice above. Rendered outside the
          indexStatus branches below (it applies whether prep is still
          running or already finished) rather than folded into either
          one, since it's about which *documents* are usable, not
          about whether the request to prepare them succeeded. */}
      {unreadableDocumentsNotice && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-sm text-amber-800">{unreadableDocumentsNotice}</p>
        </div>
      )}

      {indexStatus === "error" && (
        <div
          className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 ${
            isBlockedByUnreadableText ? "border-amber-200 bg-amber-50" : "border-red-200 bg-red-50"
          }`}
        >
          <p className={`text-sm ${isBlockedByUnreadableText ? "text-amber-800" : "text-red-700"}`}>
            {isBlockedByUnreadableText ? indexError : `Couldn't prepare ${documentsLabel} for chat. ${indexError}`}
          </p>
          {/* No "Try again" when every selected document has no
              readable text — it's a fact about the documents'
              content, not a transient prep failure, so retrying calls
              the same (skipped, client-side-only) check and gets the
              same answer every time. */}
          {!isBlockedByUnreadableText && (
            <button onClick={prepareChat} className={SECONDARY_BUTTON_CLASSES}>
              Try again
            </button>
          )}
        </div>
      )}

      {indexStatus !== "error" && (
        <>
          <div className="relative min-h-0 flex-1">
            <div
              ref={messagesContainerRef}
              onScroll={handleMessagesScroll}
              className="h-full max-h-[28rem] space-y-4 overflow-y-auto rounded-lg bg-slate-50/60 p-4 lg:max-h-none"
            >
              {messages.length === 0 && indexStatus === "ready" && (
                <p className="text-sm text-slate-500">
                  Ask a question about the selected {documentsLabel} to get started.
                </p>
              )}

              {messages.map((message, index) => (
                <ChatMessageBubble
                  key={message.id}
                  message={message}
                  isLast={index === messages.length - 1}
                  isSending={isSending}
                  copiedMessageId={copiedMessageId}
                  onCopy={handleCopyMessage}
                  onRegenerate={handleRegenerate}
                />
              ))}

              {isSending && (
                <div className="flex justify-start">
                  <div
                    className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-slate-200 bg-surface px-4 py-3"
                    role="status"
                  >
                    <span className="sr-only">Thinking…</span>
                    <span
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.3s]"
                      aria-hidden="true"
                    />
                    <span
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.15s]"
                      aria-hidden="true"
                    />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300" aria-hidden="true" />
                  </div>
                </div>
              )}
            </div>

            {showScrollToLatest && (
              <button
                type="button"
                onClick={() => {
                  scrollMessagesToBottom();
                  setShowScrollToLatest(false);
                }}
                className="absolute bottom-3 left-1/2 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-slate-900/90 px-3 py-1.5 text-xs font-medium text-white shadow-lg backdrop-blur transition-colors hover:bg-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
                  <path
                    fillRule="evenodd"
                    d="M10 3a.75.75 0 0 1 .75.75v9.69l2.72-2.72a.75.75 0 1 1 1.06 1.06l-4 4a.75.75 0 0 1-1.06 0l-4-4a.75.75 0 1 1 1.06-1.06l2.72 2.72V3.75A.75.75 0 0 1 10 3Z"
                    clipRule="evenodd"
                  />
                </svg>
                Scroll to latest
              </button>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex shrink-0 items-end gap-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleQuestionKeyDown}
              disabled={inputDisabled}
              placeholder={
                indexStatus === "indexing"
                  ? `Preparing ${documentsLabel}...`
                  : `Ask about the selected ${documentsLabel}...`
              }
              // maxHeight is a hard CSS ceiling that backs up the
              // scrollHeight-based sizing in the auto-grow effect
              // above; overflow-y-auto only actually shows a
              // scrollbar once content exceeds that ceiling, so a
              // short prompt never gets one. This is also what
              // guarantees a long pasted prompt stays fully
              // reviewable — scrollable inside the box — instead of
              // extending up past the visible composer. break-words
              // (issue 4) stops a single very long unbroken token
              // (a URL, a hash) from pushing the box wider instead of
              // wrapping — textareas already soft-wrap normal text on
              // their own, but not an unbroken run with no spaces to
              // wrap at.
              style={{ maxHeight: `${COMPOSER_MAX_HEIGHT_PX}px` }}
              className="min-w-0 flex-1 resize-none overflow-y-auto whitespace-pre-wrap break-words rounded-2xl border border-slate-300 px-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 transition-[height] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-60"
            />
            {isSending ? (
              <button
                type="button"
                onClick={handleStop}
                className="inline-flex shrink-0 items-center gap-2 rounded-full border border-slate-300 bg-surface px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset"
              >
                <span className="h-2 w-2 rounded-sm bg-slate-500" aria-hidden="true" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={inputDisabled || !question.trim()}
                className="inline-flex shrink-0 items-center gap-2 rounded-full bg-accent-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
              >
                Send
              </button>
            )}
          </form>
        </>
      )}
    </div>
  );
}

export default ChatPanel;
