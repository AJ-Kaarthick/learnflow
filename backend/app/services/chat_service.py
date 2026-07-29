"""
Orchestrates a single grounded question-answer turn over one or more
documents: resolve what to search for (query_condensation.py, new in
Milestone 6 — see below), retrieve relevant chunks (retrieval_service.py,
still unchanged in shape, generalized to take a list of document ids),
build a prompt that restricts the model to only that context plus a
short window of recent conversation, and generate an answer
(AIProvider, unchanged).

Deliberately thin: this module owns exactly one new thing — turning
"chunks (possibly from several documents) + a question (+ recent
history)" into a grounded prompt — and reuses everything else.
Retrieval and generation stay separate responsibilities (this file
calls both, but is neither): retrieve_relevant_chunks() still knows
nothing about chat or conversation history, and AIProvider still knows
nothing about where its prompt's context came from.

Milestone 6 — conversational retrieval: Milestone 5 shipped multi-
document chat and diagnosed a real limitation — retrieve_relevant_chunks
was always called with the raw current-turn question, so a follow-up
like "Explain it." retrieved chunks for the literal phrase "Explain
it." instead of whatever "it" referred to, even though the history
already sent to the model made the reference obvious to a human. This
module now closes that gap with one added step: before retrieval,
query_condensation.condense_query() turns "question + recent history"
into a standalone search query ("Explain how the ls command works").
That resolved query is used ONLY to decide what to retrieve.
build_chat_prompt below still receives the user's original, unedited
`question` — the model always answers the question the user actually
asked, grounded only in whatever retrieval found, exactly as before.
Conversation history still never becomes a source of facts; it now
additionally helps decide what to search for, which is a retrieval
concern, not a grounding one.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Document
from app.services.ai.base_provider import AIProvider
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.rag.query_condensation import condense_query
from app.services.rag.retrieval_service import DEFAULT_TOP_K, ScoredChunk, retrieve_relevant_chunks

# One prior turn: {"role": "user" | "assistant", "content": str}. Kept
# as a plain dict rather than a dataclass/schema — the service layer
# shouldn't depend on app.schemas (that's the API layer's concern; see
# routes_chat.py, which converts ChatHistoryTurn -> this shape before
# calling answer_question), and a two-key dict needs no more structure
# than that to be self-explanatory.
HistoryTurn = dict[str, str]

# How many of the most recent history turns are actually sent to the
# model, regardless of how many the caller provides — this is the
# "short-term" in short-term memory. Kept small on purpose: each turn
# adds tokens (and therefore cost/latency) to every subsequent request,
# and a handful of exchanges is enough to resolve the kind of
# follow-up this milestone targets ("explain that more simply", "give
# an example") without the prompt growing unbounded over a long
# conversation. Raising this later (or replacing it with a
# summarized/long-term memory strategy) is a one-line, one-file change
# — nothing about answer_question's or build_chat_prompt's signature
# needs to change to support that.
MAX_HISTORY_TURNS = 6

# Returned verbatim when there's no context to answer from at all (see
# answer_question below), and also given to the model as the exact
# sentence to use when retrieved context doesn't answer the question
# (see build_chat_prompt). One fixed string for both paths means a
# caller sees the same "not in the document" phrase regardless of
# which of the two produced it.
NO_CONTEXT_ANSWER = "I couldn't find the answer to this question in the uploaded document."


@dataclass
class ChatAnswer:
    answer: str
    chunks: list[ScoredChunk]
    # False only when there was no retrieved context at all to ground
    # an answer in (see answer_question). True whenever the model was
    # actually called with context — including when that context
    # wasn't enough and the model said so via NO_CONTEXT_ANSWER; that
    # is a grounded answer (the model correctly reported what the
    # document does or doesn't say), just not a positive one.
    grounded: bool


def build_chat_prompt(
    question: str,
    chunks: list[ScoredChunk],
    documents_by_id: dict[str, Document],
    history: list[HistoryTurn] | None = None,
) -> str:
    # Every excerpt is labeled with its source document's filename, not
    # just a bare index. For a single document this is a little
    # redundant (every label names the same file) but harmless; for
    # multiple documents it's what lets the model actually compare
    # across them ("deadlocks in Operating Systems" vs "deadlocks in
    # DBMS") instead of seeing an undifferentiated pile of excerpts —
    # one prompt format handles both cases rather than branching.
    context = "\n\n".join(
        f"[Excerpt {index + 1} — {documents_by_id[scored.chunk.document_id].original_filename}]\n"
        f"{scored.chunk.content}"
        for index, scored in enumerate(chunks)
    )

    history_section = ""
    if history:
        turns = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history)
        # Explicitly scoped to "what is the user referring to", not "what
        # did we say before" — history is for resolving pronouns and
        # follow-ups like "explain that more simply", never a substitute
        # source of facts. Without this framing, a model could quote its
        # own earlier (possibly-already-hedged) answer instead of
        # re-checking the excerpts, which would quietly weaken grounding.
        history_section = (
            "Recent conversation, for understanding what the current "
            "question is referring to (e.g. \"it\", \"that\", \"more "
            "simply\") only. It is NOT a source of facts — every factual "
            f"claim in your answer must still come from the document "
            f"excerpts below:\n{turns}\n\n"
        )

    return (
        "You are answering a student's question using ONLY the document "
        "excerpts below. Do not use any outside knowledge, and do not "
        "guess or make anything up. Each excerpt is labeled with the "
        "document it came from — if the question asks you to compare "
        "documents, or your answer otherwise needs to refer to a "
        "document, call it by its filename (e.g. \"the excerpt from "
        "ls.pdf\" or \"ls.pdf says...\") — never by a generic label like "
        "\"Document 1\" or \"the first document\". If the excerpts do not "
        "contain enough information to answer the question, respond with "
        "exactly this "
        f'sentence and nothing else: "{NO_CONTEXT_ANSWER}"\n\n'
        f"Document excerpts:\n{context}\n\n"
        f"{history_section}"
        f"Question: {question}\n\n"
        "Answer:"
    )


async def answer_question(
    documents: list[Document],
    question: str,
    db: Session,
    ai_provider: AIProvider,
    embedding_provider: EmbeddingProvider,
    top_k: int = DEFAULT_TOP_K,
    history: list[HistoryTurn] | None = None,
) -> ChatAnswer:
    """
    Retrieves the chunks most relevant to `question` across every
    document in `documents` and asks the AI provider to answer using
    only those chunks, optionally taking a short window of recent
    conversation into account so follow-up questions ("explain that
    more simply") don't need to repeat the original topic.

    `documents` — plural — is what makes this multi-document chat:
    single-document chat (routes_chat.py's original endpoint) is just
    the len(documents) == 1 case of this same function, not a separate
    code path. `top_k` here means "up to top_k chunks per document",
    not "top_k chunks total" — see retrieve_relevant_chunks for why —
    so a question about N documents can surface up to N * top_k chunks.

    `history` is frontend-managed, not persisted: the caller (see
    routes_chat.py) sends whatever it's currently holding in memory,
    and only the most recent MAX_HISTORY_TURNS entries are actually
    used — see that constant's comment for why. This function doesn't
    validate ordering or pairing of `history`; it trusts the caller to
    send turns oldest-first, which is what a client replaying its own
    conversation state naturally does.

    Milestone 6: what gets *retrieved* and what gets *asked* are no
    longer necessarily the same string. `condense_query` (see
    query_condensation.py) turns `question` + `recent_history` into a
    standalone query and that's what's searched for — but `question`
    itself, unedited, is still what's sent to the model in
    build_chat_prompt below. A follow-up like "Explain it." is
    therefore retrieved as if the user had asked "Explain how the ls
    command works" (whatever the resolved topic is), while the model
    still sees, and answers, the literal "Explain it." it was asked —
    resolving what to search for is a retrieval concern; resolving
    what the user meant when generating the reply was already handled,
    unchanged, by history_section in build_chat_prompt.
    """
    document_ids = [document.id for document in documents]
    recent_history = history[-MAX_HISTORY_TURNS:] if history else []
    retrieval_query = await condense_query(question, recent_history, ai_provider)

    chunks = await retrieve_relevant_chunks(
        document_ids=document_ids,
        query=retrieval_query,
        db=db,
        embedding_provider=embedding_provider,
        top_k=top_k,
    )

    if not chunks:
        # No indexed chunks for any of these documents — there's no
        # context an AI call could possibly ground an answer in, so
        # skip the call rather than risk it answering from outside
        # knowledge. (Routes should generally reject un-indexed
        # documents before this is ever reached — see routes_chat.py —
        # but this keeps the service itself safe to call directly too.)
        return ChatAnswer(answer=NO_CONTEXT_ANSWER, chunks=[], grounded=False)

    documents_by_id = {document.id: document for document in documents}
    prompt = build_chat_prompt(question, chunks, documents_by_id, recent_history)
    answer = await ai_provider.generate_text(prompt)

    return ChatAnswer(answer=answer.strip(), chunks=chunks, grounded=True)
