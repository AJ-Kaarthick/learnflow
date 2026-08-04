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

Milestone 3 (V2.2) — intelligent multi-document retrieval: two
additions here build on retrieval_service.py's new adaptive budget,
relevance signal, and deduplication, without disturbing anything
above. First, is_comparison_question() detects comparison-style
questions ("compare X and Y", "what's the difference between...") and
build_chat_prompt appends a dedicated set of instructions for them on
top of the existing grounding preamble — comparison questions still
get every rule normal questions get (ONLY the excerpts, the fixed
NO_CONTEXT_ANSWER fallback, filenames over generic labels), plus
explicit instructions to compare, attribute facts to documents, and
call out when only some selected documents are relevant. Second,
answer_question now uses retrieval's per-document relevance summary to
turn a generic "not found" answer into an informative one when the
underlying documents genuinely differ in relevance (see
_build_informative_no_match_answer) — the model isn't asked to guess
at this; it comes from retrieval's own scoring.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Document
from app.services.ai.base_provider import AIProvider
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.rag.query_condensation import condense_query
from app.services.rag.retrieval_service import (
    DocumentRetrievalSummary,
    ScoredChunk,
    retrieve_relevant_chunks,
)

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

# --------------------------------------------------------------------
# Comparison-question detection (Milestone 3, requirement 5)
# --------------------------------------------------------------------
#
# Matched as whole words/phrases, case-insensitively, against the raw
# question the user typed — not the condensed retrieval query, since
# condensation's job is "what to search for," and whether this is a
# comparison question is about what kind of *answer* the user wants,
# which is a prompt-construction concern (build_chat_prompt), not a
# retrieval one. Deliberately over-inclusive rather than exact: a
# false positive just means a normal question gets a few extra
# comparison-framing instructions it happens not to need (harmless —
# the underlying grounding rules are identical either way), while a
# false negative means a genuine comparison question is answered
# without them, which is the failure mode actually worth avoiding.
_COMPARISON_QUESTION_PATTERN = re.compile(
    r"\b("
    r"compare|comparison|comparing|"
    r"difference|differences|differing|"
    r"similarit(?:y|ies)|"
    r"pros and cons|advantage|advantages|disadvantage|disadvantages|"
    r"across (?:the )?documents|which document|versus|vs\.?"
    r")\b",
    re.IGNORECASE,
)


def is_comparison_question(question: str) -> bool:
    """Whether `question` is asking to compare/contrast across documents — see the pattern above."""
    return bool(_COMPARISON_QUESTION_PATTERN.search(question))


# Appended to the normal grounding preamble (never replacing it) when
# is_comparison_question(question) is true AND more than one document
# is in play — see build_chat_prompt. Every rule the normal prompt
# already enforces (ONLY the excerpts, the fixed NO_CONTEXT_ANSWER
# fallback, filenames over generic labels) still applies unchanged;
# this only adds what a comparison specifically needs on top of that.
_COMPARISON_PROMPT_ADDITION = (
    "This question asks you to compare across the selected documents. "
    "In your answer:\n"
    "- Directly compare the documents: call out both similarities and "
    "differences, not just a summary of each one in turn.\n"
    "- For every factual claim, say which document it comes from, by "
    "filename.\n"
    "- If only some of the selected documents actually contain "
    "information relevant to the question, say so explicitly — name "
    "which documents contributed relevant information and which did "
    "not, rather than writing the comparison as if every document "
    "weighed in equally.\n\n"
)


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
    # One DocumentRetrievalSummary per requested document, in request
    # order, from retrieval_service.py — carried through so a caller
    # (routes_chat.py) can build grouped source metadata and explain
    # per-document relevance without re-deriving it from `chunks`
    # alone, which may no longer include every document once
    # deduplication has run. Empty only when answer_question's history
    # default made no retrieval call at all — never the case for any
    # real request, since retrieve_relevant_chunks always returns one
    # summary per document_id it was given.
    document_summaries: list[DocumentRetrievalSummary] = field(default_factory=list)


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

    # Only meaningful when there's actually more than one document to
    # compare — a comparison-worded question about a single selected
    # document has nothing to contrast, so the extra instructions
    # would be noise rather than help. Gated on the full requested
    # document set (documents_by_id), not just the documents that
    # happen to appear in `chunks` — a document that contributed no
    # relevant evidence is exactly the case
    # _COMPARISON_PROMPT_ADDITION's last bullet exists to handle.
    comparison_section = ""
    if len(documents_by_id) > 1 and is_comparison_question(question):
        comparison_section = _COMPARISON_PROMPT_ADDITION

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
        f"{comparison_section}"
        f"Document excerpts:\n{context}\n\n"
        f"{history_section}"
        f"Question: {question}\n\n"
        "Answer:"
    )


def _describe_document_relevance(
    documents_by_id: dict[str, Document],
    document_summaries: list[DocumentRetrievalSummary],
) -> tuple[list[str], list[str]]:
    """
    Splits `document_summaries` into (filenames with relevant evidence,
    filenames without), preserving each group's relative order from
    document_summaries. Used only to build the informative fallback
    answer below — never fed back into the prompt or treated as a
    factual claim itself, it's purely a restatement of retrieval's own
    per-document scoring.
    """
    relevant: list[str] = []
    not_relevant: list[str] = []
    for summary in document_summaries:
        filename = documents_by_id[summary.document_id].original_filename
        if summary.has_relevant_evidence:
            relevant.append(filename)
        else:
            not_relevant.append(filename)
    return relevant, not_relevant


def _build_informative_no_match_answer(relevant: list[str], not_relevant: list[str]) -> str:
    """
    Replaces a generic NO_CONTEXT_ANSWER with one that says which of
    the selected documents actually had relevant evidence and which
    didn't (Milestone 3, requirement 6) — e.g. "I found relevant
    information in 2 of 3 selected documents (a.pdf, b.pdf), but not
    in: c.pdf." rather than a bare "I couldn't find the answer."

    Only ever called when relevant and not_relevant together cover
    every selected document and at least one document lacks relevant
    evidence — see answer_question for the exact gating.
    """
    total = len(relevant) + len(not_relevant)

    if not relevant:
        joined = ", ".join(not_relevant)
        return (
            f"I couldn't find information relevant to this question in any of "
            f"the {total} selected documents ({joined})."
        )

    relevant_joined = ", ".join(relevant)
    not_relevant_joined = ", ".join(not_relevant)
    return (
        f"I found relevant information in {len(relevant)} of {total} selected "
        f"documents ({relevant_joined}), but not in the following: "
        f"{not_relevant_joined}."
    )


async def answer_question(
    documents: list[Document],
    question: str,
    db: Session,
    ai_provider: AIProvider,
    embedding_provider: EmbeddingProvider,
    top_k: int | None = None,
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
    Passing `None` (the default) hands the decision to
    retrieval_service.compute_adaptive_top_k, which scales that budget
    down as more documents are selected instead of using one fixed
    number regardless of how many documents are in play — see that
    function's docstring. A caller that passes an explicit `top_k`
    (e.g. a client-specified value on the chat request) always gets
    exactly that value honored, same as before this milestone.

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

    Milestone 3 (V2.2): when more than one document is selected and
    the model still falls back to the fixed NO_CONTEXT_ANSWER sentence,
    that answer is upgraded to name which selected documents actually
    had relevant evidence and which didn't — but only when retrieval's
    own per-document scoring draws that distinction (i.e. at least one
    document scored as relevant and at least one didn't). If every
    document looked equally (ir)relevant by that scoring, there's no
    more informative story retrieval itself can tell than the model
    already gave, so its verbatim answer is left alone — this is
    deliberately a strict upgrade of an existing fallback, never a
    second-guessing of an answer the model actually gave.
    """
    document_ids = [document.id for document in documents]
    recent_history = history[-MAX_HISTORY_TURNS:] if history else []
    retrieval_query = await condense_query(question, recent_history, ai_provider)

    retrieval_result = await retrieve_relevant_chunks(
        document_ids=document_ids,
        query=retrieval_query,
        db=db,
        embedding_provider=embedding_provider,
        top_k=top_k,
    )
    chunks = retrieval_result.chunks

    if not chunks:
        # No indexed chunks for any of these documents — there's no
        # context an AI call could possibly ground an answer in, so
        # skip the call rather than risk it answering from outside
        # knowledge. (Routes should generally reject un-indexed
        # documents before this is ever reached — see routes_chat.py —
        # but this keeps the service itself safe to call directly too.)
        return ChatAnswer(
            answer=NO_CONTEXT_ANSWER,
            chunks=[],
            grounded=False,
            document_summaries=retrieval_result.document_summaries,
        )

    documents_by_id = {document.id: document for document in documents}
    prompt = build_chat_prompt(question, chunks, documents_by_id, recent_history)
    answer = (await ai_provider.generate_text(prompt)).strip()

    if len(documents) > 1 and answer == NO_CONTEXT_ANSWER:
        relevant, not_relevant = _describe_document_relevance(
            documents_by_id, retrieval_result.document_summaries
        )
        # Only upgrade the generic fallback when retrieval's own
        # scoring actually distinguishes at least one document as
        # lacking relevant evidence. If every document scored as
        # relevant, there's nothing more informative to say than the
        # model's own verbatim answer — see this function's docstring.
        if not_relevant:
            answer = _build_informative_no_match_answer(relevant, not_relevant)

    return ChatAnswer(
        answer=answer,
        chunks=chunks,
        grounded=True,
        document_summaries=retrieval_result.document_summaries,
    )
