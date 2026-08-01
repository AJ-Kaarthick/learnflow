import { useEffect, useRef, useState } from "react";
import { indexDocument, sendChatMessage, sendMultiDocumentChatMessage } from "../api/chat";
import { clearConversation, getConversationKey, loadConversation, saveConversation } from "../utils/persistence";
import ExpandableText from "./ExpandableText";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-40";

// How close to the bottom (in pixels) still counts as "at the
// bottom" for auto-scroll purposes — a few pixels of rounding/
// sub-pixel scroll slack shouldn't count as the user having
// deliberately scrolled up.
const BOTTOM_THRESHOLD_PX = 56;

// Very small, dependency-free formatting for assistant answers: splits
// on blank lines into paragraphs, turns a block of "- "/"* " lines into
// a real list, and renders **bold** spans — enough to make lists and
// emphasis in a model's answer readable instead of every line
// (including "- point one", "- point two") running together inside one
// pre-wrapped block. Not a full markdown parser — headings, links,
// code fences, etc. are left as plain text — this only covers the
// patterns AI-generated answers actually tend to use.
function renderInline(text, keyPrefix) {
  const segments = text.split(/(\*\*[^*]+\*\*)/g).filter((segment) => segment.length > 0);
  return segments.map((segment, index) =>
    segment.startsWith("**") && segment.endsWith("**") ? (
      <strong key={`${keyPrefix}-${index}`} className="font-semibold text-slate-900">
        {segment.slice(2, -2)}
      </strong>
    ) : (
      <span key={`${keyPrefix}-${index}`}>{segment}</span>
    )
  );
}

function renderMessageContent(content) {
  const blocks = content.split(/\n{2,}/);

  return blocks.map((block, blockIndex) => {
    const lines = block.split("\n").filter((line) => line.trim().length > 0);
    const isBulletList = lines.length > 0 && lines.every((line) => /^[-*]\s+/.test(line.trim()));

    if (isBulletList) {
      return (
        <ul key={blockIndex} className="list-disc space-y-1 pl-5">
          {lines.map((line, lineIndex) => (
            <li key={lineIndex}>
              {renderInline(line.trim().replace(/^[-*]\s+/, ""), `${blockIndex}-${lineIndex}`)}
            </li>
          ))}
        </ul>
      );
    }

    return (
      <p key={blockIndex} className="whitespace-pre-wrap">
        {renderInline(block, `${blockIndex}`)}
      </p>
    );
  });
}

// Renders one turn of the conversation. Kept inside this file rather
// than a separate component file, same as every other panel's small
// per-item renderers (e.g. flashcard cards in FlashcardsPanel) —
// reusable within the panel without needing its own file.
function ChatMessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[92%] space-y-2 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-accent-600 px-4 py-2.5 text-sm leading-relaxed text-white"
              : message.isError
                ? "rounded-2xl rounded-tl-sm border border-red-200 bg-red-50 px-4 py-2.5 text-sm leading-relaxed text-red-700"
                : "space-y-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-surface px-4 py-2.5 text-sm leading-relaxed text-slate-800"
          }
        >
          {renderMessageContent(message.content)}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <details className="group rounded-xl border border-slate-200 bg-surface text-xs text-slate-600">
            <summary className="cursor-pointer select-none list-none px-3 py-2 font-medium text-slate-500 marker:content-none hover:text-slate-700">
              <span className="inline-flex items-center gap-1">
                Sources ({message.sources.length})
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.24 4.5a.75.75 0 0 1-1.08 0l-4.24-4.5a.75.75 0 0 1 .02-1.06Z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
            </summary>
            <ul className="space-y-2.5 border-t border-slate-100 px-3 py-2.5">
              {message.sources.map((source) => (
                <li key={source.chunk_id} className="rounded-lg bg-slate-50 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    {/* Only present for multi-document chat (see MultiDocumentSourceItem
                        in schemas/chat.py) — single-document sources omit it since
                        there's only one document to begin with. */}
                    {source.document_name && (
                      <p className="truncate font-medium text-slate-600">
                        {source.document_name}
                      </p>
                    )}
                    <span className="shrink-0 rounded-full bg-surface px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-slate-400">
                      {Math.round(source.score * 100)}% match
                    </span>
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
  const documentIds = documents.map((document) => document.id);
  const isMultiDocument = documentIds.length > 1;

  // One conversation per unique set of documents, keyed by sorted
  // document ids (never filenames — see getConversationKey). Stable
  // across this component's whole lifetime: AssistantPanel remounts
  // ChatPanel (via its `key`) whenever the document selection
  // actually changes, so `documents` — and therefore this key — never
  // changes out from under an already-mounted instance.
  const conversationKey = getConversationKey(documentIds);

  const [indexStatus, setIndexStatus] = useState("indexing"); // indexing | ready | error
  const [indexError, setIndexError] = useState("");

  // Restored lazily from storage on mount rather than always starting
  // at [] — this is what makes returning to a document (or document
  // combination) bring its previous conversation back automatically.
  const [messages, setMessages] = useState(() => loadConversation(conversationKey));
  const [question, setQuestion] = useState("");
  const [sendStatus, setSendStatus] = useState("idle"); // idle | sending

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
    setIndexStatus("indexing");
    setIndexError("");
    try {
      // Every selected document needs to be indexed before it can be
      // searched — each call is independent (a document indexed for
      // one conversation stays indexed), so these run in parallel
      // rather than one at a time.
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

  async function handleSubmit(event) {
    event.preventDefault();
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

    const userMessage = { id: `${Date.now()}-user`, role: "user", content: trimmedQuestion };
    setMessages((previous) => [...previous, userMessage]);
    setQuestion("");
    setSendStatus("sending");
    // Sending a message is always something the user wants to follow,
    // regardless of where they were scrolled — same as ChatGPT/Gemini,
    // the act of sending re-anchors the view to the bottom.
    isAtBottomRef.current = true;
    setShowScrollToLatest(false);

    try {
      // Single document keeps using the original, unchanged endpoint
      // (POST /documents/{id}/chat) — same call as before multi-
      // document chat existed. Multiple documents use the new
      // POST /documents/chat, which also returns which document each
      // source came from (see ChatMessageBubble).
      const result = isMultiDocument
        ? await sendMultiDocumentChatMessage(documentIds, trimmedQuestion, { history })
        : await sendChatMessage(documentIds[0], trimmedQuestion, { history });

      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: result.answer,
          sources: result.sources,
        },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content: error.message,
          isError: true,
        },
      ]);
    } finally {
      setSendStatus("idle");
    }
  }

  // Starts a fresh conversation for the *current* chat context only.
  // Deliberately narrow: it clears `messages` and this conversation's
  // entry in storage, and nothing else — not other conversations
  // (they're stored under their own keys), not this document's
  // summary/flashcards/quiz/mind map (entirely separate state, owned
  // by StudyWorkspace's panels, never touched here).
  function handleNewConversation() {
    setMessages([]);
    clearConversation(conversationKey);
    setQuestion("");
    isAtBottomRef.current = true;
    setShowScrollToLatest(false);
  }

  const isSending = sendStatus === "sending";
  const inputDisabled = indexStatus !== "ready" || isSending;
  const documentsLabel = isMultiDocument ? "documents" : "document";

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-tight text-slate-900">Chat</h3>
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

      {indexStatus === "error" && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2">
          <p className="text-sm text-red-700">
            Couldn&apos;t prepare {documentsLabel} for chat. {indexError}
          </p>
          <button onClick={prepareChat} className={SECONDARY_BUTTON_CLASSES}>
            Try again
          </button>
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

              {messages.map((message) => (
                <ChatMessageBubble key={message.id} message={message} />
              ))}

              {isSending && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-surface px-4 py-2.5 text-sm text-slate-500">
                    <span
                      className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-accent-600"
                      aria-hidden="true"
                    />
                    Thinking...
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

          <form onSubmit={handleSubmit} className="flex shrink-0 items-center gap-2">
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={inputDisabled}
              placeholder={
                indexStatus === "indexing"
                  ? `Preparing ${documentsLabel}...`
                  : `Ask about the selected ${documentsLabel}...`
              }
              className="min-w-0 flex-1 rounded-full border border-slate-300 px-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={inputDisabled || !question.trim()}
              className="inline-flex shrink-0 items-center gap-2 rounded-full bg-accent-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-inset disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </>
      )}
    </div>
  );
}

export default ChatPanel;
