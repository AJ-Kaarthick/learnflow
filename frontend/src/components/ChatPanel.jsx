import { useEffect, useRef, useState } from "react";
import { indexDocument, sendChatMessage, sendMultiDocumentChatMessage } from "../api/chat";

const SECONDARY_BUTTON_CLASSES =
  "rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40";

// Renders one turn of the conversation. Kept inside this file rather
// than a separate component file, same as every other panel's small
// per-item renderers (e.g. flashcard cards in FlashcardsPanel) —
// reusable within the panel without needing its own file.
function ChatMessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={
            isUser
              ? "rounded-lg bg-accent-600 px-3 py-2 text-sm text-white"
              : message.isError
                ? "rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                : "rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800"
          }
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <details className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <summary className="cursor-pointer select-none font-medium text-slate-500">
              Sources ({message.sources.length})
            </summary>
            <ul className="mt-2 space-y-2">
              {message.sources.map((source) => (
                <li key={source.chunk_id} className="border-t border-slate-100 pt-2 first:border-t-0 first:pt-0">
                  {/* Only present for multi-document chat (see MultiDocumentSourceItem
                      in schemas/chat.py) — single-document sources omit it since
                      there's only one document to begin with. */}
                  {source.document_name && (
                    <p className="mb-1 font-medium text-slate-500">{source.document_name}</p>
                  )}
                  <p className="line-clamp-3 text-slate-600">{source.content}</p>
                  <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
                    {Math.round(source.score * 100)}% match
                  </p>
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

  const [indexStatus, setIndexStatus] = useState("indexing"); // indexing | ready | error
  const [indexError, setIndexError] = useState("");

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [sendStatus, setSendStatus] = useState("idle"); // idle | sending

  const messagesEndRef = useRef(null);
  // Tracks whether the scroll-to-latest-message effect below is
  // running for this panel's first render. HomePage remounts ChatPanel
  // (via its `key`) every time the document selection changes —
  // opening a document from the library, or checking/unchecking one —
  // which made the effect fire on that very first render too and pull
  // the whole page down to an empty, just-mounted chat panel the user
  // hadn't asked to see. Skipping the first run keeps the intended
  // behavior (scroll to the newest message as the conversation grows)
  // while no longer moving the page on mount.
  const isFirstRender = useRef(true);

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

  // Runs once when this panel mounts. HomePage keys ChatPanel by the
  // current document selection, so selecting a different set of
  // documents (or uploading a new one) remounts a fresh instance —
  // that's also what resets `messages` back to an empty conversation,
  // with no extra reset logic needed here.
  useEffect(() => {
    prepareChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentIds.join(",")]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
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

  const isSending = sendStatus === "sending";
  const inputDisabled = indexStatus !== "ready" || isSending;
  const documentsLabel = isMultiDocument ? "documents" : "document";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold tracking-tight text-slate-900">Chat</h2>
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
          the caller (see HomePage's chip row above this panel, which
          also lets the user remove one) — not repeated here, so the
          same information isn't shown twice back-to-back. */}

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
          <div className="max-h-96 min-h-[8rem] space-y-3 overflow-y-auto rounded-lg bg-slate-50/50 p-3">
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
                <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                  <span
                    className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-accent-600"
                    aria-hidden="true"
                  />
                  Thinking...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="flex items-center gap-2">
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={inputDisabled}
              placeholder={
                indexStatus === "indexing"
                  ? `Preparing ${documentsLabel}...`
                  : `Ask a question about the selected ${documentsLabel}...`
              }
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={inputDisabled || !question.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:opacity-40"
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
