import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { indexDocument } from "../api/chat";
import { sendConversationMessage } from "../api/conversations";
import { appendPersistedTurn, toInternalMessages } from "../utils/conversationMessages";
import { describeUnreadableDocuments, splitDocumentsByReadability } from "../utils/documentReadiness";
import ExpandableText from "./ExpandableText";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

// Small icon-only buttons under an assistant message (just Copy, as of
// V2.4 Milestone 2 — see the removed Regenerate button's note below)
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
//
// V2.4 Milestone 2 (frontend): this used to also take `isLast` and
// `onRegenerate`, to offer a "Regenerate" action on the most recent
// assistant answer. That's deliberately not carried forward into the
// persistent-conversation model: regenerating means replacing an
// already-*persisted* turn, and the backend has no endpoint yet to
// delete or amend a saved message (send_message in
// routes_conversations.py only ever appends a new turn) — building
// that is real backend surface area this phase's brief scopes out
// ("Implement the frontend Conversation Management foundation" —
// amending history isn't part of that foundation). Re-asking the same
// question is still always possible by typing it again; what's
// removed is only the illusion that doing so replaces, rather than
// adds to, the persisted history.
function ChatMessageBubble({ message, copiedMessageId, onCopy }) {
  const isUser = message.role === "user";
  const isCopied = copiedMessageId === message.id;
  const timestamp = formatTimestamp(message.createdAt);

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

        {/* Timestamp + actions row. Timestamp is optional — it only
            renders for messages that have one, so an assistant error
            bubble (which never got a persisted created_at) just shows
            the actions without a blank gap. */}
        <div className={`flex items-center gap-2 px-1 ${isUser ? "justify-end" : "justify-start"}`}>
          {timestamp && <span className="text-[11px] text-slate-400">{timestamp}</span>}
          {!isUser && !message.isError && (
            <button
              type="button"
              onClick={() => onCopy(message)}
              className={MESSAGE_ACTION_BUTTON_CLASSES}
            >
              {isCopied ? "Copied!" : "Copy"}
            </button>
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
                      {/* Only present for multi-document conversations
                          (see MessageSourceItem in
                          schemas/conversation.py) — single-document
                          sources omit it since there's only one
                          document to begin with. */}
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

// V2.4 Milestone 2 (frontend): `conversationId` and `initialMessages`
// are new — this panel is now a view onto one specific, backend-
// persisted Conversation (see api/conversations.js), not a view keyed
// off whatever documents happen to be selected. `documents` is
// unchanged in shape and purpose (still the readable/unreadable split
// below, still what gets indexed and what the composer's placeholder
// names) — it's just sourced from the active conversation's own
// associated documents now (see ChatPage.jsx), instead of free-
// floating page state.
function ChatPanel({ conversationId, initialMessages, documents, onMessageSent }) {
  // V2.4 Milestone 1 UX polish (issue 2): split the selection into
  // documents Chat can actually use vs. ones with no readable text
  // (splitDocumentsByReadability — same per-document signal Study
  // generation already gates on, see documentReadiness.js). Only the
  // readable group is ever indexed or sent to the chat endpoint
  // below, so one unreadable document in a multi-document selection
  // can never block the others (issue 3) — and unreadableDocuments is
  // what lets this panel name exactly which file(s) it left out
  // (issue 4), instead of a generic error.
  const { readable: readableDocuments, unreadable: unreadableDocuments } =
    splitDocumentsByReadability(documents);
  const documentIds = readableDocuments.map((document) => document.id);
  const isMultiDocument = documentIds.length > 1;
  const hasUsableDocuments = documentIds.length > 0;

  const [indexStatus, setIndexStatus] = useState("indexing"); // indexing | ready | error
  const [indexError, setIndexError] = useState("");

  // Initialized once, from this conversation's own persisted history
  // (see api/conversations.js's getConversation /
  // ConversationDetailResponse.messages) — never localStorage anymore.
  // AssistantPanel keys this component by `conversationId` (see
  // AssistantPanel.jsx), so a genuinely different conversation always
  // gets a fresh mount and therefore a fresh call to this initializer
  // — the same guarantee against one conversation's messages leaking
  // into another's view that toInternalMessages' own tests exercise
  // at the pure-function level (see conversationMessages.test.js).
  const [messages, setMessages] = useState(() => toInternalMessages(initialMessages));
  const [question, setQuestion] = useState("");
  const [sendStatus, setSendStatus] = useState("idle"); // idle | sending
  const [copiedMessageId, setCopiedMessageId] = useState(null);

  // The in-flight request's AbortController (Milestone 4: "Stop
  // generation"). This endpoint isn't streamed — there's no partial
  // answer to interrupt mid-token — so "stop" means "stop waiting on
  // and discard whatever comes back", not "cut off the model
  // mid-sentence". That's still a meaningful, honest version of the
  // feature for a non-streaming architecture: it immediately frees the
  // input for a new question instead of forcing a wait. As of
  // Milestone 2, the backend request behind this call also persists
  // its own turn once it completes (see send_message's docstring in
  // routes_conversations.py) — stopping only ever stops the client
  // from waiting on/using that eventual response, same caveat
  // api/conversations.js's sendConversationMessage already documents.
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
  // ChatPanel (via its `key`) every time the active conversation
  // changes, which made the effect fire on that very first render too
  // and jump straight to an empty, just-mounted chat panel the user
  // hadn't asked to see. Skipping the first run keeps the intended
  // behavior (scroll to the newest message as the conversation grows)
  // without moving anything on mount.
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

  // Runs on mount, and again whenever the active conversation's
  // associated *readable* document ids actually change — e.g. the
  // user adds or removes a document from this same conversation via
  // the library (see ChatPage.jsx's replaceConversationDocuments call)
  // without switching conversations, which no longer remounts this
  // component (see AssistantPanel.jsx's docstring on why).
  useEffect(() => {
    prepareChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentIds.join(",")]);

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
  // conversations while a question is still in flight.
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (copiedTimeoutRef.current) clearTimeout(copiedTimeoutRef.current);
    };
  }, []);

  // The actual network call, abort wiring, and success/error handling
  // for sending one message. Unlike the old client-managed-history
  // version of this function, there's no `history` to build and pass
  // — the backend loads a conversation's persisted messages itself
  // (see ConversationMessageRequest's docstring in
  // schemas/conversation.py) — so this only ever needs the question
  // text and which optimistic message to reconcile once the real,
  // persisted turn comes back (see appendPersistedTurn,
  // utils/conversationMessages.js).
  async function askQuestion(trimmedQuestion, optimisticUserId) {
    setSendStatus("sending");
    isAtBottomRef.current = true;
    setShowScrollToLatest(false);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await sendConversationMessage(conversationId, trimmedQuestion, {
        signal: controller.signal,
      });
      setMessages((previous) => appendPersistedTurn(previous, response, optimisticUserId));
      // Lets ChatPage bump this conversation to the top of the
      // sidebar list, mirroring the backend's own "sending a message
      // bumps updated_at" behavior (see send_message's docstring)
      // without a full GET /conversations round trip just to re-sort
      // a list the client already has (see
      // utils/conversationSelection.js's touchConversation) — and
      // also lets it fold `response`'s two persisted (backend-shape)
      // messages into its own cached `activeConversation.messages`.
      // That cache only otherwise gets set once, when the
      // conversation is first loaded (see ChatPage.jsx's
      // loadConversationDetail) — without this, it would go stale the
      // instant a message is sent, and AssistantPanel's own layout
      // unmounts/remounts this component whenever the document chip
      // row goes from 0 to 1+ chips for the *same* conversation (see
      // AssistantPanel.jsx), which would silently re-initialize
      // `messages` from that stale cache and appear to erase whatever
      // was just sent.
      onMessageSent?.(conversationId, response);
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

    // Shown immediately so the composer feels responsive; replaced
    // in-place by the real, persisted user message once the backend
    // responds (see askQuestion -> appendPersistedTurn above). Its id
    // only ever needs to be unique among messages currently on
    // screen — sendStatus already prevents a second send from
    // starting while this one is still in flight, so there's never
    // more than one optimistic message at a time to collide with.
    const optimisticId = `temp-${Date.now()}`;
    const userMessage = {
      id: optimisticId,
      role: "user",
      content: trimmedQuestion,
      createdAt: Date.now(),
    };
    setMessages((previous) => [...previous, userMessage]);
    setQuestion("");
    askQuestion(trimmedQuestion, optimisticId);
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

  // V2.4 Milestone 1 UX polish: the composer grows with the prompt (up
  // to COMPOSER_MAX_HEIGHT_PX, then scrolls internally instead — see
  // the textarea's `style` below) rather than staying a fixed single
  // line. Resetting to "auto" before reading scrollHeight is what
  // lets the box shrink back down again too (e.g. after clearing a
  // long question on send) — without it, scrollHeight would only
  // ever reflect the tallest the box has already been.
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
        <h3 className="text-sm font-semibold tracking-tight text-slate-900">Chat</h3>
        {indexStatus === "indexing" && (
          <span className="flex items-center gap-2 text-xs text-slate-500">
            <span
              className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-accent-600"
              aria-hidden="true"
            />
            Preparing {documentsLabel}...
          </span>
        )}
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

      {/* V2.4 Milestone 2 Phase 3 QA fix (issue 3): this used to be
          `{indexStatus !== "error" && (<>...messages + composer...</>)}`
          — an index/prep failure (most commonly: every selected
          document has no readable text) replaced the *entire* message
          area with just this banner, hiding a conversation's already-
          persisted history rather than showing it alongside the
          banner, exactly like the partial (some readable, some not)
          case already does via unreadableDocumentsNotice above.
          Persisted messages were never actually lost — `messages` was
          always correctly initialized from `initialMessages` (see the
          useState above) — they were just not rendered while blocked.
          The fix: this banner and the message list are no longer
          mutually exclusive: the banner explains what's blocked, the
          composer is disabled the exact same way it already was
          (`inputDisabled` below still gates on `indexStatus !==
          "ready"`), and the conversation's history stays visible
          underneath either way. */}
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

          {messages.map((message) => (
            <ChatMessageBubble
              key={message.id}
              message={message}
              copiedMessageId={copiedMessageId}
              onCopy={handleCopyMessage}
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
    </div>
  );
}

export default ChatPanel;
